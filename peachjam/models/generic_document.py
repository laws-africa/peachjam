from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.frbr_uri import FRBR_URI_DOCTYPES
from peachjam.models import (
    CoreDocument,
    CoreDocumentManager,
    CoreDocumentQuerySet,
    Label,
    Work,
)
from peachjam.models.author import Author


class GenericDocument(CoreDocument):
    authors = models.ManyToManyField(
        Author,
        blank=True,
        verbose_name=_("authors"),
    )

    frbr_uri_doctypes = ["doc", "statement"]

    class Meta(CoreDocument.Meta):
        verbose_name = _("generic document")
        verbose_name_plural = _("generic documents")

    def __str__(self):
        return self.title

    def get_doc_type_display(self):
        if not self.nature:
            return super().get_doc_type_display()
        return self.nature.name

    def pre_save(self):
        self.doc_type = "generic_document"
        super().pre_save()


class LegalInstrument(CoreDocument):
    authors = models.ManyToManyField(
        Author,
        blank=True,
        verbose_name=_("authors"),
    )

    frbr_uri_doctypes = [x for x in FRBR_URI_DOCTYPES if x != "judgment"]

    class Meta(CoreDocument.Meta):
        verbose_name = _("legal instrument")
        verbose_name_plural = _("legal instruments")

    def __str__(self):
        return self.title

    def get_doc_type_display(self):
        return self.nature.name

    def pre_save(self):
        self.doc_type = "legal_instrument"
        super().pre_save()


class LegislationManager(CoreDocumentManager):
    def get_queryset(self):
        # defer expensive fields
        return super().get_queryset().defer("metadata_json")


class Legislation(CoreDocument):
    objects = LegislationManager.from_queryset(CoreDocumentQuerySet)()

    metadata_json = models.JSONField(_("metadata JSON"), null=False, blank=False)
    repealed = models.BooleanField(_("repealed"), default=False, null=False)
    parent_work = models.ForeignKey(
        Work, null=True, on_delete=models.PROTECT, verbose_name=_("parent work")
    )

    frbr_uri_doctypes = ["act"]

    class Meta(CoreDocument.Meta):
        verbose_name = _("legislation")
        verbose_name_plural = _("legislation")

    def __str__(self):
        return self.title

    def search_penalty(self):
        # non-principal (ie. amendment) works get a slight search penalty so that principal works
        # tend to appear above them in search results
        if self.metadata_json and self.metadata_json.get("principal", None) is False:
            return 10.0
        return super().search_penalty()

    def apply_labels(self):
        # label to indicate that this legislation is repealed
        label, _ = Label.objects.get_or_create(
            code="repealed",
            defaults={"name": "Repealed", "code": "repealed", "level": "danger"},
        )
        # apply label if repealed
        if self.repealed:
            self.labels.add(label.pk)
        else:
            # not repealed, remove label
            self.labels.remove(label.pk)

        super().apply_labels()

    def pre_save(self):
        self.doc_type = "legislation"
        return super().pre_save()
