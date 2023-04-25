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


class RegionalEconomicCommunity(models.Model):
    locality = models.ForeignKey(
        Locality,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
    )


class MemberState(models.Model):
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name=_("country")
    )
