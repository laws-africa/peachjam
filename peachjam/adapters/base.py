import logging

import requests

logger = logging.getLogger(__name__)


class Adapter:
    def __init__(self, ingestor, settings):
        self.ingestor = ingestor
        self.settings = settings
        self.predicates = {
            "amended-by": {
                "name": "amended by",
                "verb": "is amended by",
                "reverse_verb": "amends",
            },
            "repealed-by": {
                "name": "repealed by",
                "verb": "is repealed by",
                "reverse_verb": "repeals",
            },
            "revoked-by": {
                "name": "revoked by",
                "verb": "is revoked by",
                "reverse_verb": "revokes",
            },
            "withdrawn-by": {
                "name": "withdrawn by",
                "verb": "is withdrawn by",
                "reverse_verb": "withdraws",
            },
            "lapsed-by": {
                "name": "lapsed by",
                "verb": "is lapsed by",
                "reverse_verb": "lapses",
            },
            "retired-by": {
                "name": "retired by",
                "verb": "is retired by",
                "reverse_verb": "retires",
            },
            "expired-by": {
                "name": "expired by",
                "verb": "is expired by",
                "reverse_verb": "expires",
            },
            "replaced-by": {
                "name": "replaced by",
                "verb": "is replaced by",
                "reverse_verb": "replaces",
            },
            "commenced-by": {
                "name": "commenced by",
                "verb": "is commenced by",
                "reverse_verb": "commences",
            },
        }

    def check_for_updates(self, last_refreshed):
        """Checks for documents updated since last_refreshed (which may be None), and returns a list
        of document identifiers (expression FRBR URIs) which must be updated.
        """
        raise NotImplementedError()

    def update_document(self, document_id):
        """Update the document identified by some opaque id, returned by check_for_updates."""
        raise NotImplementedError()

    def handle_webhook(self, request, data):
        """Handle webhook from a remote server."""
        pass

    def get_edit_url(self, document):
        """Get an adapter-specific edit URL for this document."""
        pass

    @classmethod
    def name(cls):
        return cls.__name__


class RequestsAdapter(Adapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = requests.session()
        self.api_url = self.settings["api_url"]

    def client_request(self, method, url, **kwargs):
        logger.debug(f"{method.upper()} {url} kwargs={kwargs}")
        r = getattr(self.client, method)(url, **kwargs)
        r.raise_for_status()
        return r

    def client_get(self, url, **kwargs):
        return self.client_request("get", url, **kwargs)

    def client_post(self, url, **kwargs):
        return self.client_request("post", url, **kwargs)
