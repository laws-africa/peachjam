from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import Author, Locality


class AfricanUnionOrgan(models.Model):
    author = models.ForeignKey(
        Author,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("author"),
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    def __str__(self):
        return self.author.name


class RegionalEconomicCommunity(models.Model):
    locality = models.ForeignKey(
        Locality,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
    )

    class Meta:
        verbose_name_plural = _("Regional economic communities")

    def __str__(self):
        return self.locality.name


class MemberState(models.Model):
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name=_("country")
    )

    def __str__(self):
        return self.country.name
