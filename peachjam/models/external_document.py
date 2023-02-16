from .core_document_model import CoreDocument


class ExternalDocument(CoreDocument):

    frbr_uri_doctypes = ["doc"]

    def save(self, *args, **kwargs):
        self.doc_type = "external"
        return super().save(*args, **kwargs)
