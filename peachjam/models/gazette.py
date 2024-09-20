from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument


class Gazette(CoreDocument):
    publication = models.CharField(
        _("publication"), max_length=100, null=True, blank=True
    )
    sub_publication = models.CharField(
        _("sub publication"), max_length=100, null=True, blank=True
    )
    supplement = models.BooleanField(_("supplement"), default=False)
    supplement_number = models.IntegerField(
        _("supplement number"), null=True, blank=True
    )
    part = models.CharField(_("part"), max_length=10, null=True, blank=True)
    # this is the unique key from Gazettes.Africa and is used to redirect old URLs
    key = models.CharField(
        _("key"), max_length=512, null=True, blank=True, db_index=True
    )
    volume_number = models.CharField(
        _("volume number"), max_length=512, null=True, blank=True
    )
    special = models.BooleanField(_("special"), default=False)

    default_nature = ("gazette", "Gazette")

    class Meta(CoreDocument.Meta):
        verbose_name = _("gazette")
        verbose_name_plural = _("gazettes")
        permissions = [("api_gazette", "API gazette access")]

    def pre_save(self):
        self.frbr_uri_doctype = "officialGazette"
        self.doc_type = "gazette"
        super().pre_save()
