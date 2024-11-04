from .core_document import CoreDocument


class ExternalDocument(CoreDocument):

    frbr_uri_doctypes = ["doc"]

    def pre_save(self):
        self.doc_type = "external"
        return super().pre_save()
