from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class LegalSubject(models.Model):
    AREA_OF_LAW = "area_of_law"
    CONCEPT = "concept"
    DOCTRINE = "doctrine"
    PROCEDURE = "procedure"
    PRINCIPLE = "principle"
    REMEDY = "remedy"
    DEFENCE = "defence"

    SUBJECT_TYPES = (
        (AREA_OF_LAW, _("Area of law")),
        (CONCEPT, _("Concept")),
        (DOCTRINE, _("Doctrine")),
        (PROCEDURE, _("Procedure")),
        (PRINCIPLE, _("Principle")),
        (REMEDY, _("Remedy")),
        (DEFENCE, _("Defence")),
    )

    name = models.CharField(_("name"), max_length=255, unique=True)
    slug = models.SlugField(_("slug"), max_length=255, unique=True, blank=True)
    description = models.TextField(_("description"), blank=True)
    subject_type = models.CharField(
        _("subject type"), max_length=32, choices=SUBJECT_TYPES
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("legal subject")
        verbose_name_plural = _("legal subjects")

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.name and not slugify(self.name):
            raise ValidationError(
                {"name": _("Name must contain at least one letter or number.")}
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class LeadingAuthority(models.Model):
    judgment = models.ForeignKey(
        "peachjam.Judgment",
        related_name="leading_authorities",
        on_delete=models.CASCADE,
        verbose_name=_("judgment"),
    )
    subject = models.ForeignKey(
        LegalSubject,
        related_name="leading_authorities",
        on_delete=models.PROTECT,
        limit_choices_to={
            "subject_type__in": (LegalSubject.DOCTRINE, LegalSubject.PRINCIPLE)
        },
        verbose_name=_("legal subject"),
    )
    editorial_note = models.TextField(_("editorial note"))
    as_at_date = models.DateField(_("reviewed as at"))
    published = models.BooleanField(_("published"), default=False)

    class Meta:
        ordering = ("subject__name", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("judgment", "subject"),
                name="unique_leading_authority_judgment_subject",
            )
        ]
        verbose_name = _("leading authority")
        verbose_name_plural = _("leading authorities")

    def __str__(self):
        return f"{self.judgment} — {self.subject}"

    @classmethod
    def published_prefetch(cls):
        return models.Prefetch(
            "leading_authorities",
            queryset=cls.objects.filter(published=True)
            .select_related("subject")
            .prefetch_related("sources"),
            to_attr="_published_leading_authorities",
        )

    def clean(self):
        super().clean()
        if self.subject_id and self.subject.subject_type not in (
            LegalSubject.DOCTRINE,
            LegalSubject.PRINCIPLE,
        ):
            raise ValidationError(
                {
                    "subject": _(
                        "A leading authority must relate to a doctrine or principle."
                    )
                }
            )


class LeadingAuthoritySource(models.Model):
    leading_authority = models.ForeignKey(
        LeadingAuthority,
        related_name="sources",
        on_delete=models.CASCADE,
        verbose_name=_("leading authority"),
    )
    citation = models.TextField(_("citation"))
    url = models.URLField(_("URL"), blank=True)

    class Meta:
        ordering = ("pk",)
        verbose_name = _("leading authority source")
        verbose_name_plural = _("leading authority sources")

    def __str__(self):
        return self.citation
