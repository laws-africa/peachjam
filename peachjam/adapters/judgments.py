import logging
from tempfile import NamedTemporaryFile

import magic
import requests
from cobalt.uri import FrbrUri
from countries_plus.models import Country
from django.core.files import File
from django.utils import timezone
from django.utils.text import slugify
from languages_plus.models import Language

from peachjam.adapters.base import RequestsAdapter
from peachjam.models import (
    CaseNumber,
    Court,
    CourtRegistry,
    DocumentTopic,
    Judge,
    Judgment,
    MatterType,
    SourceFile,
    Taxonomy,
)
from peachjam.plugins import plugins

log = logging.getLogger(__name__)


@plugins.register("ingestor-adapter")
class JudgmentAdapter(RequestsAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.filters = {}
        for pair in (self.settings.get("filters") or "").split():
            if "=" in pair:
                key, value = pair.split("=")
                self.filters[key] = value
        self.court_codes = self.settings["court_code"].split()
        self.filters["court__code"] = []
        for code in self.court_codes:
            self.filters["court__code"].append(code)

    def check_for_updates(self, last_refreshed):
        updated = self.check_for_updated(last_refreshed)
        return updated, []

    def check_for_updated(self, last_refreshed):
        log.info(f"Checking for updated decisions since {last_refreshed}")

        results = []
        params = dict(self.filters)
        if last_refreshed:
            # convert to UTC timezone and add suffix Z
            params["updated_at__gte"] = (
                last_refreshed.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
                + "Z"
            )

        url = f"{self.api_url}/judgments"
        while url:
            res = self.client_get(url, params=params).json()
            params = {}
            urls = [
                f"{self.api_url}/judgments{r['expression_frbr_uri']}"
                for r in res["results"]
            ]
            results.extend(urls)
            url = res["next"]

        log.info(f"Found {len(results)} updated decisions")
        return results

    def check_for_deleted(self, docs):
        # This is implemented in its own adapter
        return []

    def update_document(self, url):
        log.info(f"Updating judgment {url}")

        try:
            doc = self.client_get(url).json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                log.info(f"Document {url} not found, skipping")
                return
            raise e

        frbr_uri = FrbrUri.parse(doc["work_frbr_uri"])
        jurisdiction = Country.objects.get(iso__iexact=doc["jurisdiction"])
        language = Language.objects.get(iso_639_1__iexact=doc["language"])
        court, _ = Court.objects.get_or_create(
            code=doc["court"]["code"], defaults={"name": doc["court"]["name"]}
        )
        registry, _ = CourtRegistry.objects.get_or_create(
            code=doc["registry"]["code"],
            defaults={"name": doc["registry"]["name"], "court": court},
        )

        data = {
            "title": doc["title"],
            "case_name": doc["case_name"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "citation": doc["citation"],
            "auto_assign_details": False,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_actor": frbr_uri.subtype,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "serial_number": doc["serial_number"],
            "serial_number_override": doc["serial_number_override"],
            "mnc": doc["mnc"],
            "date": doc["date"],
            "metadata_json": doc,
            "content_html": self.get_content_html(doc),
            "registry": registry,
            "court": court,
            "language": language,
            "jurisdiction": jurisdiction,
        }

        document = Judgment(**data)
        document.work_frbr_uri = document.generate_work_frbr_uri()
        expression_frbr_uri = document.generate_expression_frbr_uri()

        if frbr_uri.work_uri() != document.work_frbr_uri:
            raise ValueError(
                f"FRBR URI mismatch: {frbr_uri.work_uri()} != {document.work_frbr_uri}"
            )

        created_doc, new = Judgment.objects.update_or_create(
            expression_frbr_uri=expression_frbr_uri, defaults=data
        )

        self.get_case_numbers(doc["case_numbers"], created_doc)
        self.get_judges(doc["judges"], created_doc)
        self.get_taxonomies(doc["topics"], created_doc)
        self.attach_source_file(doc, created_doc)

        log.info(f"Updated judgment {created_doc}")
        log.info(f"New {new}")

    def get_case_numbers(self, case_numbers, doc):
        CaseNumber.objects.filter(document=doc).delete()
        for case_number in case_numbers:
            if case_number["matter_type"]:
                matter_type, _ = MatterType.objects.get_or_create(
                    name=case_number["matter_type"]
                )
            else:
                matter_type = None
            CaseNumber.objects.create(
                document=doc,
                string_override=case_number["string_override"],
                matter_type=matter_type,
                year=case_number["year"],
                number=case_number["number"],
                string=case_number["string"],
            )

    def get_judges(self, judges, doc):
        doc.judges.clear()
        if judges:
            for judge in judges:
                j, _ = Judge.objects.get_or_create(name=judge)
                doc.judges.add(j)

    def get_taxonomies(self, topics, doc):
        DocumentTopic.objects.filter(document=doc).delete()
        if topics:
            for topic in topics:
                # we are not building a tree here
                taxonomy = Taxonomy.objects.filter(name=topic).first()
                if taxonomy:
                    DocumentTopic.objects.create(
                        document=doc,
                        topic=taxonomy,
                    )

    def attach_source_file(self, doc, created_doc):
        source_file_url = f"{self.api_url}{doc['expression_frbr_uri']}/source.pdf"
        try:
            r = self.client_get(source_file_url)
        except requests.exceptions.HTTPError as e:
            # ignore 404s, which means there's no source file
            if e.response.status_code == 404:
                return
            raise

        with NamedTemporaryFile() as f:
            f.write(r.content)
            f.flush()
            mimetype = magic.from_file(f.name, mime=True)
            filename = slugify(doc.title)

            sf = SourceFile.objects.update_or_create(
                document=created_doc,
                defaults={
                    "file": File(f, filename),
                    "mimetype": mimetype,
                },
            )
            sf.ensure_file_as_pdf()

    def get_content_html(self, doc):
        try:
            url = f"{self.api_url}/judgments{doc['expression_frbr_uri']}/.html"
            response = self.client_get(url).text
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return ""
            raise e

    def delete_document(self, expression_frbr_uri):
        url = f"{self.api_url}/judgments{expression_frbr_uri}"

        try:
            self.client_get(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                document = Judgment.objects.filter(
                    expression_frbr_uri=expression_frbr_uri
                ).first()
                if document:
                    document.delete()
            else:
                raise e
