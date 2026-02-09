from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from peachjam.models.core_document import CoreDocument


class ArbitralInstitution(models.Model):
    name = models.CharField(max_length=255)
    acronym = models.CharField(max_length=50, blank=True, unique=True)
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    headquarters_city = models.CharField(max_length=255, blank=True)
    is_internationally_recognized = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.acronym})" if self.acronym else self.name

    def get_absolute_url(self):
        return reverse("arbitral_institution_detail", args=[self.acronym])


class ArbitrationSeat(models.Model):
    city = models.CharField(max_length=255)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    slug = models.SlugField(unique=True, max_length=255)
    is_new_york_convention_signatory = models.BooleanField(
        default=True, help_text=_("Can awards be enforced in 170+ countries.")
    )

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

    case_number = models.CharField(max_length=100, unique=True)

    institution = models.ForeignKey(
        ArbitralInstitution, on_delete=models.PROTECT, related_name="cases"
    )

    seat = models.ForeignKey(
        ArbitrationSeat,
        on_delete=models.SET_NULL,
        null=True,
    )

    applicable_law = models.CharField(max_length=255, blank=True)

    claimants_country_of_origin = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name="awards_as_claimants",
    )

    respondents_county_of_origin = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        related_name="awards_as_respondents",
    )

    rules_of_arbitration = models.ForeignKey(
        "peachjam.CoreDocument",
        related_name="arbitration_rules",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    case_type = models.CharField(
        max_length=50,
        choices=CaseType.choices,
    )

    award_type = models.CharField(
        max_length=50, choices=AwardType.choices, null=True, blank=True
    )

    nature_of_proceedings = models.CharField(
        max_length=50,
        choices=ArbitrationNature.choices,
    )

    outcome = models.CharField(
        max_length=50, choices=Outcome.choices, null=True, blank=True
    )

    class Meta:
        verbose_name = "Arbitration Award"

    def __str__(self):
        return f"Award for {self.case_number} ({self.get_outcome_display()})"

    def get_absolute_url(self):
        return reverse("arbitration_award_detail", args=[self.case_number])
