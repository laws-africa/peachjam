from .core_document import CoreDocument, Perms


class ExternalDocument(CoreDocument):

    frbr_uri_doctypes = ["doc"]

    class Meta(CoreDocument.Meta):
        permissions = Perms.permissions

    def pre_save(self):
        self.doc_type = "external"
        return super().pre_save()
