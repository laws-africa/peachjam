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

    def handle_webhook(self, data):
        """Handle webhook from a remote server."""
        pass

    def get_edit_url(self, document):
        """Get an adapter-specific edit URL for this document."""
        pass

    @classmethod
    def name(cls):
        return cls.__name__
