from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from peachjam.models import BreadCrumb, CoreDocument


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

    def get_breadcrumbs(self):

        breadcrumbs = super().get_breadcrumbs()
        breadcrumbs.append(
            BreadCrumb(
                name=_("Gazette"),
                url=reverse("gazettes"),
            )
        )
        breadcrumbs.append(
            BreadCrumb(
                name=str(self.jurisdiction),
                url=reverse(
                    "gazettes_by_locality", args=[self.jurisdiction.pk.lower()]
                ),
            )
        )
        if self.locality:
            breadcrumbs.append(
                BreadCrumb(
                    name=str(self.locality),
                    url=reverse(
                        "gazettes_by_locality", args=[self.locality.place_code]
                    ),
                )
            )
            breadcrumbs.append(
                BreadCrumb(
                    name=str(self.date.year),
                    url=reverse(
                        "gazettes_by_year",
                        args=[self.locality.place_code, self.date.year],
                    ),
                )
            )
        elif settings.PEACHJAM["MULTIPLE_JURISDICTIONS"]:
            breadcrumbs.append(
                BreadCrumb(
                    name=str(self.date.year),
                    url=reverse(
                        "gazettes_by_year",
                        args=[self.jurisdiction.pk.lower(), self.date.year],
                    ),
                )
            )
        else:
            breadcrumbs.append(
                BreadCrumb(
                    name=str(self.date.year),
                    url=reverse("gazettes_by_year", args=[self.date.year]),
                )
            )
        return breadcrumbs
