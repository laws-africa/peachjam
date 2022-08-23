from django.db import models

from peachjam.frbr_uri import FRBR_URI_DOCTYPES
from peachjam.models import CoreDocument, Work
from peachjam.models.author import Author


class DocumentNature(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class GenericDocument(CoreDocument):
    author = models.ForeignKey(Author, on_delete=models.PROTECT, null=True, blank=True)
    nature = models.ForeignKey(
        DocumentNature, on_delete=models.PROTECT, null=False, blank=False
    )

    frbr_uri_doctypes = ["doc", "statement"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "generic_document"
        return super().save(*args, **kwargs)


class LegalInstrument(CoreDocument):
    author = models.ForeignKey(Author, on_delete=models.PROTECT, null=True, blank=True)
    nature = models.ForeignKey(
        DocumentNature, on_delete=models.PROTECT, null=False, blank=False
    )

    frbr_uri_doctypes = [x for x in FRBR_URI_DOCTYPES if x != "judgment"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "legal_instrument"
        return super().save(*args, **kwargs)


class Legislation(CoreDocument):
    metadata_json = models.JSONField(null=False, blank=False)
    repealed = models.BooleanField(default=False, null=False)
    parent_work = models.ForeignKey(Work, null=True, on_delete=models.PROTECT)

    frbr_uri_doctypes = ["act"]

    class Meta:
        verbose_name_plural = "Legislation"

    @property
    def get_taxonomies(self):
        return list(
            self.taxonomies.distinct("topic").values_list("topic__name", flat=True)
        )

    @property
    def get_year(self):
        return self.date.year

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "legislation"
        return super().save(*args, **kwargs)
