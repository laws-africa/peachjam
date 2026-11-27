import hashlib
import logging
from datetime import date

import requests
from cobalt.uri import FrbrUri
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from languages_plus.models import Language

from peachjam.models import Gazette, SourceFile, get_country_and_locality
from peachjam.plugins import plugins
from peachjam_api.permissions import CoreDocumentPermission

from .base import RequestsAdapter

logger = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GazetteAPIAdapter(RequestsAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jurisdiction = self.settings.get("jurisdiction")
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of urls which must be updated.
        """
        docs = self.get_updated_docs(last_refreshed)
        urls = [d["url"] for d in docs]
        return urls, []

    def get_updated_docs(self, last_refreshed):
        results = []
        # self.jurisdiction can be a space-separated list of jurisdiction codes or an empty string for all jurisdictions
        for juri in (self.jurisdiction or "").split() or [None]:
            logger.info(
                f"Checking for new gazettes from Gazettes.Africa since {last_refreshed} for jurisdiction {juri}"
            )

            params = {}
            if last_refreshed:
                params["updated_at__gte"] = last_refreshed.isoformat()

            if juri:
                if juri.endswith("-*"):
                    # handle jurisdiction wildcards, eg za-*
                    # instead of asking for a jurisdiction code, we must ask for a specific
                    # country and all jurisdictions under it
                    params["country"] = juri.split("-")[0]
                    params["locality__isnull"] = False
                else:
                    params["jurisdiction"] = juri

            url = f"{self.api_url}/gazettes/archived.json"
            while url:
                res = self.client_get(url, params=params).json()
                params = {}
                results.extend(res["results"])
                url = res["next"]

        return results

    def update_document(self, url):
        logger.info(f"Updating gazette ... {url}")
        if url.endswith("/"):
            url = url[:-1]

        try:
            document = self.client_get(f"{url}.json").json()
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                return
            else:
                raise error

        frbr_uri = FrbrUri.parse(document["expression_frbr_uri"])
        country, locality = get_country_and_locality(document["jurisdiction"])
        language = Language.objects.get(pk=document["language"])

        data = {
            "jurisdiction": country,
            "locality": locality,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_actor": frbr_uri.actor,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": date.fromisoformat(document["date"]),
            "title": document["name"],
            "publication": document["publication"],
            "sub_publication": document["sub_publication"],
            "supplement": document["supplement"],
            "supplement_number": document["supplement_number"],
            "part": document["part"],
            "key": document["key"],
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
            "ingestor": self.ingestor,
        }
        gazette, new = Gazette.objects.update_or_create(
            expression_frbr_uri=document["expression_frbr_uri"],
            defaults={**data},
        )

        if frbr_uri.expression_uri() != gazette.expression_frbr_uri:
            raise Exception(
                f"FRBR URIs do not match: {frbr_uri.expression_uri()} != {gazette.expression_frbr_uri}"
            )

        logger.info(f"New document: {new}")

        s3_file = "s3:" + document["s3_location"].replace("/", ":", 1)
        # Let storage handle downloads rather than persisting the service's download_url.
        sf, created = SourceFile.objects.update_or_create(
            document=gazette,
            defaults={
                "file": s3_file,
                "mimetype": "application/pdf",
                "filename": document["key"] + ".pdf",
                "size": document["size"],
            },
        )
        # force the dynamic file field to be set correctly
        SourceFile.objects.filter(pk=sf.pk).update(file=s3_file)

        # we update directly in the db, so fake the file_changed hook
        sf.refresh_from_db()
        sf.file_changed()

        logger.info("Done.")

    def delete_document(self, frbr_uri):
        url = f"{self.api_url}{frbr_uri}"

        try:
            self.client_get(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                document = Gazette.objects.filter(expression_frbr_uri=frbr_uri).first()
                if document:
                    document.delete()
            else:
                raise e

    def handle_webhook(self, request, data):
        from peachjam.tasks import delete_document, update_document

        # check perms
        if not CoreDocumentPermission().has_permission(request, None):
            logger.warning("Unauthorized webhook request")
            return

        logger.info(f"Ingestor {self.ingestor} handling webhook {data}")

        if data.get("action") == "updated" and data.get("gazette", {}).get("url"):
            logger.info("Will update document")
            update_document(self.ingestor.pk, data["gazette"]["url"])

        if data.get("action") == "deleted" and data.get("gazette", {}).get("frbr_uri"):
            logger.info("Will delete document")
            delete_document(self.ingestor.pk, data["gazette"]["frbr_uri"])


@plugins.register("ingestor-adapter")
class PeachjamGazetteAdapter(RequestsAdapter):
    """Import gazettes and their PDFs from another Peachjam site, such as Kenya Law."""

    metadata_fields = (
        "title",
        "publication",
        "sub_publication",
        "supplement",
        "supplement_number",
        "part",
        "volume_number",
        "special",
        "published",
        "allow_robots",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_url = self.api_url.rstrip("/")
        self.client.headers["Authorization"] = f"Token {self.settings['token']}"

    def check_for_updates(self, last_refreshed):
        """Import incremental changes; leave historical reconciliation to export comparison."""
        if last_refreshed is None:
            # Ingestor.check_for_updates records this refresh's start time as the cutoff.
            return [], []
        params = {}
        params["updated_at__gte"] = last_refreshed.isoformat()
        if self.settings.get("jurisdiction"):
            params["jurisdiction"] = self.settings["jurisdiction"]

        updated = []
        url = f"{self.api_url}/gazettes"
        while url:
            page = self.client_get(url, params=params).json()
            updated.extend(entry["expression_frbr_uri"] for entry in page["results"])
            url = page["next"]
            params = {}
        return updated, []

    def update_document(self, expression_frbr_uri):
        """Upsert a source gazette by its existing identifier, preserving its metadata."""
        url = f"{self.api_url}/gazettes{expression_frbr_uri}"
        try:
            doc = self.client_get(url).json()
        except requests.HTTPError as error:
            if error.response.status_code == 404:
                logger.info(
                    "Gazette %s no longer exists, skipping", expression_frbr_uri
                )
                return
            raise
        if doc["expression_frbr_uri"] != expression_frbr_uri:
            raise ValueError("The source returned a different gazette identifier")

        frbr_uri = FrbrUri.parse(expression_frbr_uri)
        if frbr_uri.doctype != "officialGazette":
            raise ValueError("The source document is not a gazette")
        place = frbr_uri.country
        if frbr_uri.locality:
            place += f"-{frbr_uri.locality}"
        country, locality = get_country_and_locality(place)
        data = {field: doc[field] for field in self.metadata_fields}
        data.update(
            jurisdiction=country,
            locality=locality,
            language=Language.objects.get(pk=doc["language"]),
            date=date.fromisoformat(doc["date"]),
            frbr_uri_doctype=frbr_uri.doctype,
            frbr_uri_subtype=frbr_uri.subtype,
            frbr_uri_actor=frbr_uri.actor,
            frbr_uri_date=frbr_uri.date,
            frbr_uri_number=frbr_uri.number,
            ingestor=self.ingestor,
        )
        candidate = Gazette(**data)
        candidate.work_frbr_uri = candidate.generate_work_frbr_uri()
        if candidate.generate_expression_frbr_uri() != expression_frbr_uri:
            raise ValueError("Gazette metadata does not match its source identifier")

        # Fetch and validate the PDF before creating or changing any local records.
        source_url = f"{url}/source.pdf"
        pdf = self.client_get(source_url).content
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("The source did not return a PDF for this gazette")

        with transaction.atomic():
            gazette, created = Gazette.objects.update_or_create(
                expression_frbr_uri=expression_frbr_uri, defaults=data
            )
            self.attach_pdf(gazette, source_url, pdf)
        logger.info("Imported gazette %s (new: %s)", expression_frbr_uri, created)

    def attach_pdf(self, gazette, source_url, pdf):
        """Replace the source file only when its content has changed."""
        source_file = getattr(gazette, "source_file", None)
        digest = hashlib.sha256(pdf).hexdigest()
        if source_file and source_file.file and source_file.sha256 == digest:
            if source_file.source_url != source_url:
                SourceFile.objects.filter(pk=source_file.pk).update(
                    source_url=source_url
                )
            return

        filename = f"{slugify(gazette.title)[:200] or 'gazette'}.pdf"
        source_file = source_file or SourceFile(document=gazette)
        source_file.track_changes()
        source_file.file = ContentFile(pdf, name=filename)
        source_file.filename = filename
        source_file.mimetype = "application/pdf"
        source_file.size = len(pdf)
        source_file.source_url = source_url
        source_file.save()


@plugins.register("ingestor-adapter")
class PeachjamGazetteDeleteAdapter(PeachjamGazetteAdapter):
    """Check Kenyan gazettes against Kenya Law using the judgment deletion workflow."""

    def queryset(self):
        return Gazette.objects.filter(jurisdiction_id="KE")

    def check_for_updates(self, last_refreshed):
        """Queue batched existence checks for all Kenyan gazettes, including shared history."""
        from peachjam.tasks import get_deleted_documents

        batch_size = int(self.settings.get("batch_range") or 10000)
        if batch_size < 1:
            raise ValueError("batch_range must be positive")
        pks = list(self.queryset().order_by("pk").values_list("pk", flat=True))
        for start in range(0, len(pks), batch_size):
            batch = pks[start : start + batch_size]
            get_deleted_documents(self.ingestor.pk, batch[0], batch[-1])
        return [], []

    def get_deleted_documents(self, range_start, range_end):
        """Validate an inclusive primary-key range without shifting after earlier deletions."""
        from peachjam.tasks import delete_document

        uris = list(
            self.queryset()
            .filter(pk__gte=range_start, pk__lte=range_end)
            .order_by("pk")
            .values_list("expression_frbr_uri", flat=True)
        )
        if not uris:
            return
        result = self.client_post(
            f"{self.api_url}/validate-gazette-expression-frbr-uris",
            json={"expression_frbr_uris": uris},
        ).json()
        # Do not trust a remote response to expand the local deletion scope.
        for uri in set(result["invalid_expression_frbr_uris"]).intersection(uris):
            delete_document(self.ingestor.pk, uri)

    def delete_document(self, expression_frbr_uri):
        """Re-check existence immediately before deleting a local Kenyan gazette."""
        gazette = (
            self.queryset().filter(expression_frbr_uri=expression_frbr_uri).first()
        )
        if gazette is None:
            return
        try:
            self.client_get(f"{self.api_url}/gazettes{expression_frbr_uri}")
        except requests.HTTPError as error:
            if error.response.status_code != 404:
                raise
            logger.info("Deleting Kenyan gazette %s", expression_frbr_uri)
            gazette.delete()
