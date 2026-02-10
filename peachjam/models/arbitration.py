from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from peachjam.models.core_document import CoreDocument


class ArbitralInstitution(models.Model):
    name = models.CharField(_("name"), max_length=255)
    acronym = models.CharField(_("acronym"), max_length=50, blank=True, unique=True)
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    headquarters_city = models.CharField(
        _("headquarters city"), max_length=255, blank=True
    )
    is_internationally_recognized = models.BooleanField(
        _("internationally recognized"),
        default=False,
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("arbitral institution")
        verbose_name_plural = _("arbitral institutions")

    def __str__(self):
        return f"{self.name} ({self.acronym})" if self.acronym else self.name

    def get_absolute_url(self):
        return reverse("arbitral_institution_detail", args=[self.acronym])


class ArbitrationSeat(models.Model):
    city = models.CharField(_("city"), max_length=255)
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, verbose_name=_("country")
    )
    slug = models.SlugField(_("slug"), unique=True, max_length=255)
    is_new_york_convention_signatory = models.BooleanField(
        _("New York Convention signatory"),
        default=True,
        help_text=_("Can awards be enforced in 170+ countries."),
    )

    class Meta:
        ordering = ("city", "country")
        verbose_name = _("arbitration seat")
        verbose_name_plural = _("arbitration seats")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.city}-{self.country.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.city}, {self.country.name}"


class ArbitrationAward(CoreDocument):
    class CaseType(models.TextChoices):
        INVESTOR_STATE = "INVESTOR_STATE", "Investor State"
        COMMERCIAL = "COMMERCIAL", "Commercial Arbitration"
        INT_INVESTOR_AGREEMENT = "IIA", "International Investor Agreement"

    class AwardType(models.TextChoices):
        FINAL = "FINAL", "Final Award"
        INTERIM = "INTERIM", "Interim Award"
        PARTIAL = "PARTIAL", "Partial Award"

    class ArbitrationNature(models.TextChoices):
        DOMESTIC = "DOMESTIC", "Domestic"
        INTERNATIONAL = "INTERNATIONAL", "International"

    class Outcome(models.TextChoices):
        CLAIMANT = "CLAIMANT", "In Favour of Claimant"
        RESPONDENT = "RESPONDENT", "In Favour of Respondent"

    case_number = models.CharField(_("case number"), max_length=100, unique=True)

    institution = models.ForeignKey(
        ArbitralInstitution,
        on_delete=models.PROTECT,
        related_name="cases",
        verbose_name=_("institution"),
    )

    seat = models.ForeignKey(
        ArbitrationSeat,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("seat"),
    )

    applicable_law = models.CharField(_("applicable law"), max_length=255, blank=True)

    claimants_country_of_origin = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name="awards_as_claimants",
        verbose_name=_("claimants country of origin"),
    )

    respondents_country_of_origin = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name="awards_as_respondents",
        verbose_name=_("respondents country of origin"),
    )

    rules_of_arbitration = models.ForeignKey(
        "peachjam.CoreDocument",
        related_name="arbitration_rules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("rules of arbitration"),
    )

    case_type = models.CharField(
        _("case type"),
        max_length=50,
        choices=CaseType.choices,
    )

    award_type = models.CharField(
        _("award type"),
        max_length=50,
        choices=AwardType.choices,
        null=True,
        blank=True,
    )

    nature_of_proceedings = models.CharField(
        _("nature of proceedings"),
        max_length=50,
        choices=ArbitrationNature.choices,
    )

    outcome = models.CharField(
        _("outcome"),
        max_length=50,
        choices=Outcome.choices,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("arbitration award")
        verbose_name_plural = _("arbitration awards")

    def build_case_number(self):
        if not self.institution or not self.case_number:
            return self.case_number

        institution_part = self.institution.acronym or self.institution.name
        prefix = slugify(institution_part)
        if self.case_number.startswith(f"{prefix}-"):
            return self.case_number
        return slugify(f"{prefix}-{self.case_number}")

    def pre_save(self):
        self.case_number = self.build_case_number()
        return super().pre_save()

    def __str__(self):
        return f"Award for {self.case_number} ({self.get_outcome_display()})"

    def get_absolute_url(self):
        return reverse("arbitration_award_detail", args=[self.case_number])
