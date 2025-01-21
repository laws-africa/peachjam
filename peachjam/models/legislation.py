from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import (
    CoreDocument,
    CoreDocumentManager,
    CoreDocumentQuerySet,
    Label,
    Perms,
    Work,
)


class LegislationManager(CoreDocumentManager):
    def get_queryset(self):
        # defer expensive fields
        return super().get_queryset().defer("timeline_json", "commencements_json")


class Legislation(CoreDocument):
    objects = LegislationManager.from_queryset(CoreDocumentQuerySet)()

    timeline_json = models.JSONField(
        _("timeline JSON"), null=False, blank=False, default=list
    )
    commencements_json = models.JSONField(
        _("commencements JSON"), null=False, blank=False, default=list
    )
    repealed = models.BooleanField(_("repealed"), default=False, null=False)
    parent_work = models.ForeignKey(
        Work, null=True, on_delete=models.PROTECT, verbose_name=_("parent work")
    )
    principal = models.BooleanField(_("principal"), default=False, null=False)

    frbr_uri_doctypes = ["act"]

    default_nature = ("act", "Act")

    class Meta(CoreDocument.Meta):
        verbose_name = _("legislation")
        verbose_name_plural = _("legislation")
        permissions = Perms.permissions

    def __str__(self):
        return self.title

    def search_penalty(self):
        # non-principal (ie. amendment) works get a slight search penalty so that principal works
        # tend to appear above them in search results
        if self.metadata_json and self.metadata_json.get("principal", None) is False:
            return 10.0
        return super().search_penalty()

    @property
    def commenced(self):
        return self.metadata_json.get("commenced", None)

    def apply_labels(self):
        labels = list(self.labels.all())

        # label to indicate that this legislation is repealed
        repealed_label, _ = Label.objects.get_or_create(
            code="repealed",
            defaults={"name": "Repealed", "code": "repealed", "level": "danger"},
        )
        uncommenced_label, _ = Label.objects.get_or_create(
            code="uncommenced",
            defaults={
                "name": "Uncommenced",
                "level": "danger",
            },
        )

        # apply label if repealed
        if self.repealed:
            if repealed_label not in labels:
                self.labels.add(repealed_label.pk)
        elif repealed_label in labels:
            # not repealed, remove label
            self.labels.remove(repealed_label.pk)

        # apply label if not commenced
        if not self.commenced:
            if uncommenced_label not in labels:
                self.labels.add(uncommenced_label.pk)
        elif uncommenced_label in labels:
            self.labels.remove(uncommenced_label.pk)

        super().apply_labels()

    def pre_save(self):
        self.doc_type = "legislation"
        return super().pre_save()
