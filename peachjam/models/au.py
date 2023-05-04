from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _


class AfricanUnionOrgan(models.Model):
    author = models.ForeignKey(
        "peachjam.Author",
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
        "peachjam.Locality",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        verbose_name_plural = _("Regional economic communities")

    def __str__(self):
        return self.locality.name


class MemberState(models.Model):
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name=_("country")
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    code = models.SlugField(_("code"), max_length=1024, editable=False, unique=True)

    def __str__(self):
        return self.country.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.country.iso
        return super().save(*args, **kwargs)
