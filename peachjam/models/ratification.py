from countries_plus.models import Country
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from peachjam.models import Work, pj_settings


class Ratification(models.Model):
    work = models.OneToOneField(
        Work,
        related_name="ratification",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        verbose_name=_("work"),
    )
    source_url = models.URLField(
        _("source URL"), null=True, blank=True, max_length=2048
    )
    last_updated = models.DateField(_("last updated"), null=True, blank=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("ratification")
        verbose_name_plural = _("ratifications")
        permissions = [("api_ratification", "API ratification access")]

    @cached_property
    def n_ratified(self):
        return self.countries.filter(ratification_date__isnull=False).count()

    @cached_property
    def n_signed(self):
        return self.countries.filter(signature_date__isnull=False).count()

    @cached_property
    def n_deposited(self):
        return self.countries.filter(deposit_date__isnull=False).count()

    def countries_list(self):
        """Same as .countries buts but the current site country (if any) at the top."""
        this_country = pj_settings().default_document_jurisdiction
        return sorted(
            list(self.countries.all()),
            key=lambda c: "" if c.country == this_country else c.country.name,
        )

    def __str__(self):
        return f"{self.work}"


class RatificationCountry(models.Model):
    ratification = models.ForeignKey(
        Ratification,
        related_name="countries",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        verbose_name=_("ratification"),
    )
    country = models.ForeignKey(
        Country,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        verbose_name=_("country"),
    )
    ratification_date = models.DateField(_("ratification date"), null=True, blank=True)
    deposit_date = models.DateField(_("deposit date"), null=True, blank=True)
    signature_date = models.DateField(_("signature date"), null=True, blank=True)

    class Meta:
        verbose_name = _("ratification country")
        verbose_name_plural = _("ratification countries")
        ordering = ["country__name"]
        unique_together = [["ratification", "country"]]

    def __str__(self):
        return f"{self.country} - {self.ratification.work}"
