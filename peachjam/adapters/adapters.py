import logging
from tempfile import NamedTemporaryFile

import magic
import requests
from django.core.files import File

from peachjam.plugins import plugins

logger = logging.getLogger(__name__)


class Adapter:
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
    def __init__(self, url, token):
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {token}",
            }
        )
        self.url = url

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        updated_docs_list = self.get_updated_documents(last_refreshed)
        return [d["expression_frbr_uri"] for d in updated_docs_list]

    def get_doc_list(self):
        return self.client_get(self.url).json()["results"]

    def get_updated_documents(self, last_refreshed):
        if last_refreshed is None:
            return self.get_doc_list()

        return [d for d in self.get_doc_list() if d["updated_at"] > last_refreshed]

    def update_document(self, expression_frbr_uri):
        from countries_plus.models import Country
        from languages_plus.models import Language

        from africanlii.models import Legislation
        from peachjam.models import Locality

        url = self.url + expression_frbr_uri + ".json"
        logger.info(f"Updating document ... {url}")

        document = self.client_get(url)
        toc_json = self.client_get(document["url"] + "/toc.json").json()["toc"]
        content_html = self.client_get(document["url"] + "/eng.html").text
        jurisdiction = Country.objects.get(iso__iexact=document["country"])
        language = Language.objects.get(iso_639_3__iexact=document["language"])
        locality = Locality.objects.get(code=document["locality"])

        field_data = {
            "title": document["title"],
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
            "work_frbr_uri": document["frbr_uri"],
            "date": document["expression_date"],
            "content_html_is_akn": True,
            "source_url": document["publication_document"]["url"]
            if document["publication_document"]
            else None,
            "metadata_json": document,
            "jurisdiction": jurisdiction,
            "locality": locality,
            "language": language,
            "toc_json": toc_json["toc"],
            "content_html": content_html,
        }

        doc = Legislation.objects.update_or_create(
            expression_frbr_uri=expression_frbr_uri, defaults={**field_data}
        )
        if document["publication_document"]:
            self.download_source_file(document["publication_document"], doc)

    def client_get(self, url):
        r = self.client.get(url)
        r.raise_for_status()
        return r

    def download_source_file(self, publication_document, doc):
        from peachjam.models import SourceFile

        filename = publication_document["filename"]
        source_url = publication_document["url"]

        logger.info(f"Downloading source file {filename}")

        with NamedTemporaryFile() as f:
            r = self.client_get(source_url)
            f.write(r.content)

            SourceFile.objects.update_or_create(
                document=doc,
                defaults={
                    "file": File(f, name=filename),
                    "mimetype": magic.from_file(f.name, mime=True),
                },
            )
