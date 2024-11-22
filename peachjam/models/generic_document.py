from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument
from peachjam.models.author import Author


class GenericDocument(CoreDocument):
    author = models.ManyToManyField(
        Author,
        blank=True,
        verbose_name=_("authors"),
    )

    frbr_uri_doctypes = ["doc", "statement"]

    default_nature = ("document", "Document")

    author_label = Author.model_label
    author_label_plural = Author.model_label_plural

    class Meta(CoreDocument.Meta):
        verbose_name = _("generic document")
        verbose_name_plural = _("generic documents")

    def __str__(self):
        return self.title

    def author_list(self):
        return list(self.author.all())

    def pre_save(self):
        self.doc_type = "generic_document"
        super().pre_save()
