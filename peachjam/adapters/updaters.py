import logging

import magic
import requests

from africanlii.download import download_source_file
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
        self.base_url = "https://api.laws.africa/v2/"

    def update_document(self, document):
        from countries_plus.models import Country

        from africanlii.models import Legislation
        from peachjam.models import Locality

        logger.info(f"Updating document ... {document['frbr_uri']} ")
        field_data = {
            "title": document["title"],
            "created_at": document["created_at"],
            "updated_at": document["updated_at"],
            "work_frbr_uri": document["frbr_uri"],
            "expression_frbr_uri": document["expression_frbr_uri"],
            "jurisdiction": Country.objects.get(iso_code=document["country"]),
            "locality": Locality.objects.get(name=document["locality"]),
            "date": document["expression_date"],
            "content_html_is_akn": True,
            "toc": self.client_get(document["frbr_uri"] + "/toc.json"),
            "content_html": self.get_html(document["frbr_uri"] + "/eng.html"),
            "source_url": document["publication_document"]["url"],
        }

        Legislation.objects.create(**field_data)

        if document["publication_document"]:
            # self.download_source_file(document["publication_document"]["url"], doc.id)
            pass

    def client_get(self, url):
        r = self.client.get(url).json()
        r.raise_for_status()
        return r

    def download_source_file(self, publication_document, doc):
        source_url = publication_document["url"]
        filename = publication_document["filename"]
        logger.info(f"Downloading source file {filename}")

        f = download_source_file(source_url)
        source_file = SourceFile.objects.create(
            document=doc,
            file=f,
            mimetype=magic.from_file(f.name, mime=True),
        )

        return source_file
