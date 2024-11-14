from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument
from peachjam.models.author import Author


class GenericDocument(CoreDocument):
    authors = models.ManyToManyField(
        Author,
        blank=True,
        verbose_name=_("authors"),
    )

    frbr_uri_doctypes = ["doc", "statement"]

    default_nature = ("document", "Document")

    class Meta(CoreDocument.Meta):
        verbose_name = _("generic document")
        verbose_name_plural = _("generic documents")

    def __str__(self):
        return self.title

    def pre_save(self):
        self.doc_type = "generic_document"
        super().pre_save()
