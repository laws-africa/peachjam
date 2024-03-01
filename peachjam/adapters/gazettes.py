import logging
from datetime import date

import requests
from cobalt.uri import FrbrUri
from countries_plus.models import Country
from languages_plus.models import Language

from peachjam.models import (
    CoreDocument,
    DocumentContent,
    DocumentNature,
    Gazette,
    Locality,
    SourceFile,
    get_country_and_locality,
)
from peachjam.plugins import plugins

from .base import Adapter

log = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class GazetteAdapter(Adapter):
    def __init__(self, settings):
        super().__init__(settings)
        self.jurisdiction = self.settings["jurisdiction"]

    def check_for_updates(self, last_refreshed):
        log.info(
            f"Checking for new gazettes from Gazettes.Africa since {last_refreshed}"
        )

        # start building queryset for updated gazettes
        updated_qs = (
            CoreDocument.objects.filter(doc_type="gazette")
            .non_polymorphic()
            .using("gazettes_africa")
        )
        # start building queryset for deleted gazettes
        deleted_qs = Gazette.objects

        if "-" not in self.jurisdiction:
            # locality code not specified hence None e.g "ZA"
            updated_qs = updated_qs.filter(
                jurisdiction=self.jurisdiction, locality=None
            )
            deleted_qs = deleted_qs.filter(
                jurisdiction=self.jurisdiction, locality=None
            )
        else:
            updated_qs = updated_qs.filter(jurisdiction=self.jurisdiction.split("-")[0])
            deleted_qs = deleted_qs.filter(jurisdiction=self.jurisdiction.split("-")[0])

            # locality code present e.g. "ZA-gp"
            if self.jurisdiction.split("-")[1] != "*":
                locality_code = self.jurisdiction.split("-")[1]
                updated_qs = updated_qs.filter(locality__code=locality_code)
                deleted_qs = deleted_qs.filter(locality__code=locality_code)
            else:
                # fetch all localities for this jurisdiction e.g. "ZA-*"
                updated_qs = updated_qs.exclude(locality=None)
                deleted_qs = deleted_qs.exclude(locality=None)

        updated_qs = updated_qs.values_list("expression_frbr_uri", flat=True)

        deleted_qs = deleted_qs.exclude(
            expression_frbr_uri__in=list(updated_qs)
        ).values_list("expression_frbr_uri", flat=True)

        if last_refreshed:
            updated_qs = updated_qs.filter(updated_at__gt=last_refreshed)

        return updated_qs, deleted_qs

    def update_document(self, expression_frbr_uri):
        log.info(f"Updating new gazette {expression_frbr_uri}")

        ga_gazette = (
            CoreDocument.objects.filter(expression_frbr_uri=expression_frbr_uri)
            .using("gazettes_africa")
            .non_polymorphic()
            .first()
        )

        if ga_gazette:
            data = {
                "title": ga_gazette.title,
                "date": ga_gazette.date,
                "source_url": ga_gazette.source_url,
                "citation": ga_gazette.citation,
                "content_html_is_akn": ga_gazette.content_html_is_akn,
                "language": Language.objects.get(pk=ga_gazette.language.pk),
                "jurisdiction": Country.objects.get(pk=ga_gazette.jurisdiction.pk),
                "work_frbr_uri": ga_gazette.work_frbr_uri,
                "frbr_uri_subtype": ga_gazette.frbr_uri_subtype,
                "frbr_uri_actor": ga_gazette.frbr_uri_actor,
                "frbr_uri_date": ga_gazette.frbr_uri_date,
                "frbr_uri_number": ga_gazette.frbr_uri_number,
                "expression_frbr_uri": ga_gazette.expression_frbr_uri,
            }

            if ga_gazette.locality:
                data["locality"] = Locality.objects.get(code=ga_gazette.locality.code)

            if ga_gazette.nature:
                document_nature_name = " ".join(
                    [name for name in ga_gazette.nature.name.split("-")]
                ).capitalize()
                data["nature"] = DocumentNature.objects.get_or_create(
                    code=ga_gazette.nature.code,
                    defaults={"name": document_nature_name},
                )[0]

            updated_gazette, new = Gazette.objects.update_or_create(
                expression_frbr_uri=expression_frbr_uri, defaults={**data}
            )

            ga_source_file = (
                SourceFile.objects.filter(document=ga_gazette)
                .values("file", "filename", "size", "mimetype")
                .using("gazettes_africa")
            )

            file_path = ga_source_file[0].pop("file")

            if ga_source_file:
                source_url = f"https://gazettes.africa{expression_frbr_uri}/source"
                updated_source_file, _ = SourceFile.objects.update_or_create(
                    document=updated_gazette,
                    defaults={"file": f"{file_path}", "source_url": source_url},
                )
                # update the source file to include the bucket name
                updated_source_file.file.set_raw_value(file_path)

            if hasattr(ga_gazette, "document_content"):
                ga_content_text = ga_gazette.document_content.content_text
                DocumentContent.objects.update_or_create(
                    document=updated_gazette, content_text=ga_content_text
                )
            updated_gazette.extract_citations()

            log.info("Update Done.")

    def delete_document(self, expression_frbr_uri):
        ga_gazette = (
            CoreDocument.objects.filter(
                doc_type="gazette", expression_frbr_uri=expression_frbr_uri
            )
            .non_polymorphic()
            .using("gazettes_africa")
            .first()
        )
        local_gazette = Gazette.objects.filter(
            expression_frbr_uri=expression_frbr_uri
        ).first()
        if not ga_gazette and local_gazette:
            local_gazette.delete()


@plugins.register("ingestor-adapter")
class GazetteAPIAdapter(Adapter):
    def __init__(self, settings):
        super().__init__(settings)
        self.jurisdiction = self.settings.get("jurisdiction")
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.api_url = self.settings["api_url"]

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
            log.info(
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
                results.extend(res["results"])
                url = res["next"]

        return results

    def update_document(self, url):
        log.info(f"Updating gazette ... {url}")
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
            "nature": None,  # see https://github.com/laws-africa/gazettemachine/issues/172
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
        }
        gazette, new = Gazette.objects.update_or_create(
            expression_frbr_uri=document["expression_frbr_uri"],
            defaults={**data},
        )

        if frbr_uri.expression_uri() != gazette.expression_frbr_uri:
            raise Exception(
                f"FRBR URIs do not match: {frbr_uri.expression_uri()} != {gazette.expression_frbr_uri}"
            )

        log.info(f"New document: {new}")

        s3_file = "s3:" + document["s3_location"].replace("/", ":", 1)
        sf, created = SourceFile.objects.update_or_create(
            document=gazette,
            defaults={
                "file": s3_file,
                "source_url": document["download_url"],
                "mimetype": "application/pdf",
                "filename": document["key"] + ".pdf",
                "size": document["size"],
            },
        )
        # force the dynamic file field to be set correctly
        SourceFile.objects.filter(pk=sf.pk).update(file=s3_file)

        log.info("Done.")

    def delete_document(self, expression_frbr_uri):
        # TODO:
        pass

    def client_get(self, url, **kwargs):
        log.debug(f"GET {url} kwargs={kwargs}")
        r = self.client.get(url, **kwargs)
        r.raise_for_status()
        return r
