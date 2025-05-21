import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class SummariserError(Exception):
    pass


class SummariserService:
    def __init__(self):
        self.api_token = settings.PEACHJAM["LAWSAFRICA_API_KEY"]
        self.api_url = settings.PEACHJAM["EXTRACTOR_API"]

    def enabled(self):
        return self.api_token and self.api_url

    def summarise_judgment(self, document):
        if not self.enabled():
            raise SummariserError("Summariser service not configured")

        text = document.get_content_as_text()
        if not text:
            raise SummariserError("Document doesn't have any text to summarise.")

        data = {
            "expression_frbr_uri": document.expression_frbr_uri,
            "text": text,
        }
        headers = self.get_headers()
        log.info("Calling summariser service")
        resp = requests.post(
            self.api_url + "summarise/judgment",
            data=data,
            headers=headers,
        )
        log.info("Done")
        if resp.status_code != 200:
            raise SummariserError(
                f"Error calling summariser service: {resp.status_code} {resp.text}"
            )
        return resp.json()

    def get_headers(self):
        return {"Authorization": "Token " + self.api_token}
