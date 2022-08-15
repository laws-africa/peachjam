import logging
import re
from datetime import datetime
from tempfile import NamedTemporaryFile

import magic
import requests
from cobalt import FrbrUri
from dateutil import parser
from django.core.files import File
from django.utils.text import slugify

from peachjam.plugins import plugins

logger = logging.getLogger(__name__)


class Adapter:
    def __init__(self, settings):
        self.settings = settings

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        raise NotImplementedError()

    def update_document(self, document_id):
        """Update the document identified by some opaque id, returned by check_for_updates."""
        raise NotImplementedError()

    @classmethod
    def name(cls):
        return cls.__name__


@plugins.register("ingestor-adapter")
class IndigoAdapter(Adapter):
    def __init__(self, settings):
        super().__init__(settings)
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {self.settings['token']}",
            }
        )
        self.url = self.settings["url"]

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        updated_docs_list = self.get_updated_documents(last_refreshed)
        return [d["url"] for d in updated_docs_list]

    def get_doc_list(self):
        return self.client_get(self.url).json()["results"]

    def get_updated_documents(self, last_refreshed):
        if last_refreshed is None:
            return self.get_doc_list()

        return [
            document
            for document in self.get_doc_list()
            if parser.parse(document["updated_at"]) > last_refreshed
        ]

    def update_document(self, url):
        from countries_plus.models import Country
        from languages_plus.models import Language

        from peachjam.models import (
            Author,
            CoreDocument,
            DocumentNature,
            GenericDocument,
            LegalInstrument,
            Legislation,
            Locality,
        )

        logger.info(f"Updating document ... {url}")

        document = self.client_get(f"{url}.json").json()
        frbr_uri = FrbrUri.parse(document["frbr_uri"])
        title = document["title"]
        toc_json = self.get_toc_json(url)
        content_html = self.client_get(url + ".html").text
        jurisdiction = Country.objects.get(iso__iexact=document["country"])
        language = Language.objects.get(iso_639_3__iexact=document["language"])

        field_data = {
            "title": title,
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
            "content_html_is_akn": True,
            "source_url": document["publication_document"]["url"]
            if document["publication_document"]
            else None,
            "language": language,
            "toc_json": toc_json,
            "content_html": content_html,
        }

        frbr_uri_data = {
            "jurisdiction": jurisdiction,
            "frbr_uri_subtype": frbr_uri.subtype,
            "frbr_uri_number": frbr_uri.number,
            "frbr_uri_doctype": frbr_uri.doctype,
            "frbr_uri_date": frbr_uri.date,
            "language": language,
            "date": datetime.strptime(document["expression_date"], "%Y-%m-%d").date(),
        }
        if document["locality"]:
            frbr_uri_data["locality"] = Locality.objects.get(code=document["locality"])

        if frbr_uri.actor:
            frbr_uri_data["frbr_uri_actor"] = frbr_uri.actor
            field_data["author"] = Author.objects.get(code__iexact=frbr_uri.actor)

        doc = CoreDocument(**frbr_uri_data)
        doc.work_frbr_uri = doc.generate_work_frbr_uri()
        expression_frbr_uri = doc.generate_expression_frbr_uri()

        if frbr_uri.work_uri() != doc.work_frbr_uri:
            raise Exception("FRBR URIs do not match.")

        if document["nature"] == "act":
            if (
                document["subtype"] == "charter"
                or "protocol"
                or "convention"
                or "treaty"
            ):
                model = LegalInstrument
                field_data["nature"] = DocumentNature.objects.update_or_create(
                    name=document["subtype"]
                )[0]
            else:
                model = Legislation
                field_data["metadata_json"] = document
        else:
            model = GenericDocument
            field_data["nature"] = DocumentNature.objects.update_or_create(
                name=document["subtype"]
            )[0]

        logger.info(model)
        doc, new = model.objects.update_or_create(
            expression_frbr_uri=expression_frbr_uri,
            defaults={**field_data, **frbr_uri_data},
        )
        logger.info(f"New document: {new}")
        self.download_source_file(f"{url}.pdf", doc, title)

    def client_get(self, url):
        r = self.client.get(url)
        r.raise_for_status()
        return r

    def get_toc_json(self, url):
        def remove_subparagraph(d):
            if d["type"] == "paragraph" or d["basic_unit"]:
                d["children"] = []
            else:
                for kid in d["children"]:
                    remove_subparagraph(kid)

        toc_json = self.client_get(url + "/toc.json").json()["toc"]
        for i in toc_json:
            remove_subparagraph(i)
        return toc_json

    def download_source_file(self, url, doc, title):
        from peachjam.models import SourceFile

        logger.info(f"Downloading source file from {url}")

        with NamedTemporaryFile() as f:
            r = self.client_get(url)
            try:
                # sometimes this header is not present
                d = r.headers["Content-Disposition"]
                filename = re.findall("filename=(.+)", d)[0]
            except KeyError:
                filename = f"{slugify(title)}.pdf"

            f.write(r.content)

            SourceFile.objects.update_or_create(
                document=doc,
                defaults={
                    "file": File(f, name=filename),
                    "mimetype": magic.from_file(f.name, mime=True),
                },
            )
