import logging

import requests

logger = logging.getLogger(__name__)


class IndigoAdapter:
    def __init__(self, url, token, last_refreshed):
        self.client = requests.session()
        self.client.headers.update(
            {
                "Authorization": f"Token {token}",
            }
        )
        self.url = url

    def get_doc_list(self):
        r = self.client.get(self.url).json()
        return r["results"]

    def get_updated_documents(self, last_refreshed):
        updated_docs_list = []
        for document in self.get_doc_list():
            if document["updated_at"] > last_refreshed:
                updated_docs_list.append(document)
        return updated_docs_list

    def get_toc(self, url):
        print("getting toc")

    def get_html(self, url):
        pass
