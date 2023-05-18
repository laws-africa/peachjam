from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _


class AfricanUnionOrgan(models.Model):
    author = models.OneToOneField(
        "peachjam.Author",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("author"),
        related_name="au_organ",
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = ["author__name"]

    def __str__(self):
        return self.author.name


class AfricanUnionInstitution(models.Model):
    author = models.OneToOneField(
        "peachjam.Author",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("author"),
        related_name="au_institution",
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = ["author__name"]

    def __str__(self):
        return self.author.name


class RegionalEconomicCommunity(models.Model):
    locality = models.OneToOneField(
        "peachjam.Locality",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
        related_name="regional_economic_community",
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        verbose_name_plural = _("Regional economic communities")
        ordering = ["locality__name"]

    def __str__(self):
        return self.locality.name


class MemberState(models.Model):
    country = models.OneToOneField(
        Country,
        on_delete=models.PROTECT,
        verbose_name=_("country"),
        related_name="member_state",
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = ["country__name"]

    def __str__(self):
        return self.country.name
