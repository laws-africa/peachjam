from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Max
from django.template.defaultfilters import date as format_date
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override as lang_override

from peachjam.models import CoreDocument, Label, Locality


class Attorney(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("attorney")
        verbose_name_plural = _("attorneys")

    def __str__(self):
        return self.name


class Judge(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("judge")
        verbose_name_plural = _("judges")

    def __str__(self):
        return self.name


class OrderOutcome(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("order outcome")
        verbose_name_plural = _("order outcomes")

    def __str__(self):
        return self.name


class MatterType(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("matter type")
        verbose_name_plural = _("matter types")

    def __str__(self):
        return self.name


class CourtClass(models.Model):
    name = models.CharField(_("name"), max_length=100, null=False, unique=True)
    description = models.TextField(_("description"), null=True, blank=True)
    order = models.IntegerField(_("order"), null=True, blank=True)

    class Meta:
        ordering = (
            "order",
            "name",
        )
        verbose_name = _("court class")
        verbose_name_plural = _("court classes")

    def __str__(self):
        return self.name


class Court(models.Model):
    name = models.CharField(_("name"), max_length=255, null=False, unique=True)
    code = models.SlugField(_("code"), max_length=255, null=False, unique=True)
    court_class = models.ForeignKey(
        CourtClass,
        related_name="courts",
        on_delete=models.PROTECT,
        null=True,
        verbose_name=_("court class"),
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    order = models.IntegerField(_("order"), null=True, blank=True)
    country = models.ForeignKey(
        Country,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_("country"),
    )
    locality = models.ForeignKey(
        Locality,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
    )

    class Meta:
        ordering = (
            "order",
            "name",
        )
        verbose_name = _("court")
        verbose_name_plural = _("courts")

    def __str__(self):
        return self.name


class CourtRegistryManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("court")


class CourtRegistry(models.Model):
    objects = CourtRegistryManager()
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        null=True,
        related_name="registries",
        verbose_name=_("court"),
    )
    name = models.CharField(_("name"), max_length=1024, null=False, blank=False)
    code = models.SlugField(_("code"), max_length=255, null=False, unique=True)

    class Meta:
        verbose_name = _("court registry")
        verbose_name_plural = _("court registries")
        unique_together = ("court", "name")

    def __str__(self):
        return f"{self.name} - {self.court}"

    def get_absolute_url(self):
        return reverse("court_registry", args=[self.court.code, self.code])

    def save(self, *args, **kwargs):
        self.code = f"{self.court.code}-{slugify(self.name)}"
        return super().save(*args, **kwargs)


class Bench(models.Model):
    # This model is not strictly necessary, as it's almost identical to the default that Django creates
    # for a many-to-many relationship. However, by creating it, we can indicate that the ordering should
    # be on the PK of the model. This means that we can preserve the ordering of Judges as the are
    # entered in the admin interface.
    #
    # To use this effectively, views that need the judges to be ordered, should call "judgement.bench.all()"
    # and not "judgment.judges.all()".
    judgment = models.ForeignKey(
        "Judgment",
        related_name="bench",
        on_delete=models.CASCADE,
        verbose_name=_("judgment"),
    )
    judge = models.ForeignKey(Judge, on_delete=models.PROTECT, verbose_name=_("judge"))

    class Meta:
        # this is to re-use the existing table rather than creating a new one
        db_table = "peachjam_judgment_judges"
        ordering = ("pk",)
        unique_together = ("judgment", "judge")


class Judgment(CoreDocument):
    court = models.ForeignKey(
        Court, on_delete=models.PROTECT, null=True, verbose_name=_("court")
    )
    registry = models.ForeignKey(
        CourtRegistry,
        on_delete=models.PROTECT,
        null=True,
        related_name="judgments",
        blank=True,
    )
    judges = models.ManyToManyField(
        Judge, blank=True, verbose_name=_("judges"), through=Bench
    )
    lower_court_judges = models.ManyToManyField(
        Judge,
        blank=True,
        verbose_name=_("lower court judges"),
        related_name="lower_court_judgments",
    )
    attorneys = models.ManyToManyField(
        Attorney, blank=True, verbose_name=_("attorneys")
    )
    order_outcomes = models.ManyToManyField(
        OrderOutcome,
        blank=True,
    )
    case_summary = models.TextField(_("case summary"), null=True, blank=True)
    flynote = models.TextField(_("flynote"), null=True, blank=True)
    case_name = models.CharField(
        _("case name"),
        max_length=4096,
        help_text=_("Party names for use in title"),
        null=False,
        blank=False,
    )
    serial_number = models.IntegerField(
        # TODO: this must be changed to True
        _("serial number"),
        null=False,
        help_text=_("Serial number for MNC, unique for a year and an author."),
    )
    serial_number_override = models.IntegerField(
        _("serial number override"),
        null=True,
        blank=True,
        help_text=_("Specific MNC serial number assigned by the court."),
    )

    mnc = models.CharField(
        _("MNC"),
        max_length=4096,
        help_text=_("Media neutral citation"),
        null=False,
        blank=False,
    )
    hearing_date = models.DateField(null=True, blank=True)

    CITATION_DATE_FORMAT = "(j F Y)"

    MNC_FORMAT = "[{year}] {author} {serial}"
    """ Format string to use for building short MNCs. """

    frbr_uri_doctypes = ["judgment"]

    class Meta(CoreDocument.Meta):
        ordering = ["title"]
        verbose_name = _("judgment")
        verbose_name_plural = _("judgments")
        permissions = [("api_judgment", "API judgment access")]

    def __str__(self):
        return self.title

    def assign_mnc(self):
        """Assign an MNC to this judgment, if one hasn't already been assigned or if details have changed."""
        if self.date and self.court:
            if (
                self.mnc != self.generate_citation()
                or self.serial_number_override
                and self.serial_number != self.serial_number_override
            ):
                self.serial_number = self.generate_serial_number()
                self.mnc = self.generate_citation()

    def generate_serial_number(self):
        """Generate a candidate serial number for this decision, based on the delivery year and court."""
        # if there's an override, use it
        if self.serial_number_override:
            return self.serial_number_override

        # use select_for_update to lock the touched rows, to avoid a race condition and duplicate serial numbers
        query = Judgment.objects.select_for_update().filter(
            date__year=self.date.year, court=self.court
        )
        if self.pk:
            query = query.exclude(pk=self.pk)

        num = query.aggregate(num=Max("serial_number"))
        return (num["num"] or 0) + 1

    def generate_citation(self):
        return self.MNC_FORMAT.format(
            year=self.date.year, author=self.court.code, serial=self.serial_number
        )

    def generate_work_frbr_uri(self):
        # enforce certain defaults for judgment FRBR URIs
        self.frbr_uri_doctype = "judgment"
        self.frbr_uri_actor = self.court.code.lower() if self.court else None
        self.frbr_uri_date = str(self.date.year) if self.date else ""
        self.frbr_uri_number = str(self.serial_number) if self.serial_number else ""
        return super().generate_work_frbr_uri()

    def clean(self):
        self.assign_mnc()
        super().clean()

    def assign_title(self):
        """Assign an automatically generated title based on the judgment details.

        Commissioner for South African Revenue Service v Van der Merwe (211 of 2021) [2022] ZASCA 106 (30 June 2022)

        case_name: Commissioner for South African Revenue Service v Van der Merwe
        dockets: 211 of 2021
        mnc: [2022] ZASCA 106
        date: (30 June 2022);

        """
        parts = []
        if self.case_name:
            parts.append(self.case_name)

        case_number = "; ".join(n.string for n in self.case_numbers.all())
        if case_number:
            parts.append("(" + case_number + ")")

        if self.mnc:
            parts.append(self.mnc)

        if self.date:
            with lang_override(self.language.iso_639_1):
                parts.append(format_date(self.date, self.CITATION_DATE_FORMAT))

        self.title = " ".join(parts)
        self.citation = self.title

    def apply_labels(self):
        """Apply labels to this judgment based on its properties."""
        # label showing that a judgment is cited/reported in law reports, hence "more important"
        label, _ = Label.objects.get_or_create(
            code="reported",
            defaults={"name": "Reported", "code": "reported", "level": "success"},
        )

        labels = list(self.labels.all())

        # if the judgment has alternative_names, apply the "reported" label
        if self.alternative_names.exists():
            if label not in labels:
                self.labels.add(label.pk)
        # if the judgment has no alternative_names, remove the "reported" label
        elif label in labels:
            self.labels.remove(label.pk)

        super().apply_labels()

    def pre_save(self):
        # ensure registry aligns to the court
        if self.registry:
            self.court = self.registry.court

        if self.court is not None:
            if self.court.country:
                self.jurisdiction = self.court.country

            if self.court.locality:
                self.locality = self.court.locality

        self.doc_type = "judgment"
        self.assign_mnc()
        self.assign_title()
        super().pre_save()


class CaseNumber(models.Model):
    string_override = models.CharField(
        _("Full case number as printed on judgment"),
        max_length=1024,
        null=True,
        blank=True,
        help_text=_("Override for full case number string"),
    )
    string = models.CharField(_("string"), max_length=1024, null=True, blank=True)
    number = models.PositiveIntegerField(_("number"), null=True, blank=True)
    year = models.PositiveIntegerField(_("year"), null=True, blank=True)
    matter_type = models.ForeignKey(
        MatterType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("matter type"),
    )

    document = models.ForeignKey(
        Judgment,
        related_name="case_numbers",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )

    class Meta:
        ordering = ["string"]
        verbose_name = _("case number")
        verbose_name_plural = _("case numbers")

    def __str__(self):
        return str(self.string)

    def get_case_number_string(self):
        if self.string_override:
            return self.string_override

        parts = []

        if self.matter_type:
            parts.append(self.matter_type.name)

        if self.number:
            parts.append(str(self.number))

        if self.year:
            parts.append(f"of {self.year}" if parts else str(self.year))

        return " ".join(parts)

    def save(self, *args, **kwargs):
        self.string = self.get_case_number_string()
        return super().save(*args, **kwargs)
