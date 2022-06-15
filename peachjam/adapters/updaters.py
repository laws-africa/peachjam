import logging
from tempfile import NamedTemporaryFile

import magic
import requests
from django.core.files.base import File

from peachjam.models import SourceFile

logger = logging.getLogger(__name__)


class IndigoUpdater:
    def __init__(self, token):
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {token}",
            }
        )
        self.base_url = "https://api.laws.africa/v2"

    def update_document(self, document):
        from countries_plus.models import Country
        from languages_plus.models import Language

        from africanlii.models import Legislation
        from peachjam.models import Locality

        logger.info(f"Updating document ... {document['frbr_uri']} ")

        toc_json = self.client_get(
            self.base_url + document["frbr_uri"] + "/toc.json"
        ).json()
        content_html = self.client_get(
            self.base_url + document["frbr_uri"] + "/eng.html"
        ).text
        jurisdiction = Country.objects.get(iso__iexact=document["country"])
        language = Language.objects.get(iso_639_3__iexact=document["language"])
        locality = Locality.objects.get(code=document["locality"])
        expression_frbr_uri = document["expression_frbr_uri"]

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


#
