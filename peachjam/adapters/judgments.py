import logging
from tempfile import NamedTemporaryFile

import magic
import requests
from cobalt.uri import FrbrUri
from django.core.files import File
from django.utils.text import slugify

from peachjam.adapters.base import RequestsAdapter
from peachjam.models import (
    CaseNumber,
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
        for code in self.court_codes:
            self.filters["court__code"].append(code)

    def check_for_updates(self, last_refreshed):
        docs = self.get_judgments_list()
        updated = self.check_for_updated(docs, last_refreshed)
        deleted = self.check_for_deleted(docs)
        return updated, deleted

    def get_judgments_list(self):
        results = []
        url = f"{self.api_url}/judgments"
        params = dict(self.filters)

        while url:
            res = self.client_get(url, params=params).json()
            params = {}
            urls = [doc["expression_frbr_uri"] for doc in res["results"]]
            results.extend(urls)
            url = res["next"]
        return results

    def check_for_updated(self, docs, last_refreshed):
        updated = []
        for doc in docs:
            if doc["updated_at"] > last_refreshed:
                updated.append(f"{self.api_url}/judgments{doc['expression_frbr_uri']}")
        return updated

    def check_for_deleted(self, docs):
        qs = Judgment.objects.filter(court__code__in=self.court_codes)
        deleted = qs.exclude(
            expression_frbr_uri__in=[doc["expression_frbr_uri"] for doc in docs]
        ).values_list("expression_frbr_uri", flat=True)
        return deleted

    def update_document(self, url):
        log.info(f"Updating judgment {url}")

        try:
            doc = self.client_get(url).json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                log.info(f"Document {url} not found, skipping")
                return
            raise e

        frbr_uri = FrbrUri.parse(doc["frbr_uri"])

        data = {
            "title": doc["title"],
            "case_name": doc["case_name"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "citation": doc["citation"],
            "auto_assign_details": False,
            "jurisdiction": doc["jurisdiction"],
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_actor": frbr_uri.subtype,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_date": frbr_uri.date,
            "date": doc["date"],
            "metadata_json": doc,
            "content_html": self.get_content_html(doc),
        }

        doc = Judgment(**data)
        doc.wor_frbr_uri = doc.generate_work_frbr_uri()
        expression_frbr_uri = doc.generate_expression_frbr_uri()

        if frbr_uri.work_uri() != doc.work_frbr_uri:
            raise ValueError(
                f"FRBR URI mismatch: {frbr_uri.work_uri()} != {doc.work_frbr_uri}"
            )

        created_doc, new = Judgment.objects.update_or_create(
            expression_frbr_uri=expression_frbr_uri, defaults=data
        )

        self.get_case_numbers(doc["case_numbers"], created_doc)
        self.get_judges(doc["judges"], created_doc)
        self.get_taxonomies(doc["topics"], created_doc)
        self.attach_source_file(doc, created_doc)

    def get_case_numbers(self, case_numbers, doc):
        CaseNumber.objects.filter(document=doc).delete()
        for case_number in case_numbers:
            matter_type, _ = MatterType.objects.get_or_create(
                name=case_number["matter_type"]
            )
            CaseNumber.objects.create(
                document=doc,
                defaults={
                    "string_override": case_number["string_override"],
                    "matter_type": matter_type,
                    "year": case_number["year"],
                    "number": case_number["number"],
                    "string": case_number["string"],
                },
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
        source_file_url = f"{self.api_url}{doc.expression_frbr_uri}/source_file"
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
        url = f"{self.api_url}{doc.expression_frbr_uri}/text"
        response = self.client_get(url).text
        return response

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
