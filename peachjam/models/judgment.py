import logging
from urllib.parse import quote

from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Max, Prefetch
from django.template.defaultfilters import date as format_date
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override as lang_override
from django_lifecycle import AFTER_SAVE

from peachjam.analysis.summariser import JudgmentSummariser
from peachjam.decorators import CauseListDecorator, JudgmentDecorator
from peachjam.helpers import current_year
from peachjam.models import (
    CoreDocument,
    DocumentContent,
    Locality,
    SourceFile,
    on_attribute_changed,
)
from peachjam.tasks import create_anonymised_source_file_pdf, generate_judgment_summary

log = logging.getLogger(__name__)


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
    model_label = _("Judge")
    model_label_plural = _("Judges")

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

    def get_absolute_url(self):
        base_url = reverse("court", kwargs={"code": "all"})
        return f"{base_url}?judges={quote(self.name)}"


class Outcome(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("outcome")
        verbose_name_plural = _("outcomes")

    def __str__(self):
        return self.name


class CaseAction(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("case action")
        verbose_name_plural = _("case actions")

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
    slug = models.SlugField(_("slug"), max_length=255, null=False, unique=True)
    order = models.IntegerField(_("order"), null=True, blank=True)
    show_listing_page = models.BooleanField(null=False, default=False)
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = (
            "order",
            "name",
        )
        verbose_name = _("court class")
        verbose_name_plural = _("court classes")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("court_class", args=[self.slug])

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    @classmethod
    def get_court_classes_with_cause_lists(cls):
        return (
            cls.objects.filter(courts__causelists__isnull=False)
            .prefetch_related(
                Prefetch(
                    "courts",
                    queryset=Court.objects.filter(causelists__isnull=False).distinct(),
                )
            )
            .distinct()
        )


class CourtDivision(models.Model):
    name = models.CharField(_("name"), max_length=255, null=False, unique=True)
    code = models.SlugField(
        _("code"), max_length=255, null=False, blank=True, unique=True
    )
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    order = models.IntegerField(_("order"), null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        return super().save(*args, **kwargs)


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

    def clean(self):
        if self.locality and self.locality.jurisdiction != self.country:
            raise ValidationError(
                {
                    "locality": _(
                        "The locality's jurisdiction and the court's country must match."
                    )
                }
            )

    def get_absolute_url(self):
        return reverse("court", args=[self.code])


class CourtRegistryManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related("court")


class CourtRegistry(models.Model):
    model_label = _("Court registry")
    model_label_plural = _("Court registries")

    objects = CourtRegistryManager()
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        null=False,
        related_name="registries",
        verbose_name=_("court"),
    )
    name = models.CharField(_("name"), max_length=1024, null=False, blank=False)
    code = models.SlugField(_("code"), max_length=255, null=False, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("court registry")
        verbose_name_plural = _("court registries")
        unique_together = ("court", "name")

    def __str__(self):
        return f"{self.name} - {self.court}"

    def get_absolute_url(self):
        return reverse("court_registry", args=[self.court.code, self.code])

    def save(self, *args, **kwargs):
        if not self.code:
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


class LowerBench(models.Model):
    judgment = models.ForeignKey(
        "Judgment",
        related_name="lower_bench",
        on_delete=models.CASCADE,
        verbose_name=_("judgment"),
    )
    judge = models.ForeignKey(
        Judge, on_delete=models.PROTECT, verbose_name=_("lower_court_judge")
    )

    class Meta:
        ordering = ("pk",)
        unique_together = ("judgment", "judge")


class Judgment(CoreDocument):
    decorator = JudgmentDecorator()

    class CaseType(models.TextChoices):
        CRIMINAL = "criminal", _("Criminal")
        CIVIL = "civil", _("Civil")

    court = models.ForeignKey(
        Court, on_delete=models.PROTECT, null=False, verbose_name=_("court")
    )
    registry = models.ForeignKey(
        CourtRegistry,
        on_delete=models.PROTECT,
        null=True,
        related_name="judgments",
        blank=True,
    )
    division = models.ForeignKey(
        CourtDivision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="judgments",
        verbose_name=_("court division"),
    )
    case_type = models.CharField(
        _("case type"),
        max_length=512,
        choices=CaseType.choices,
        null=True,
        blank=True,
    )
    filing_year = models.PositiveIntegerField(
        _("filing year"),
        null=True,
        blank=True,
        help_text=_("Year the matter was filed (YYYY only)."),
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(limit_value=current_year),
        ],
    )
    case_action = models.ForeignKey(
        CaseAction,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="judgments",
        verbose_name=_("case action"),
    )
    judges = models.ManyToManyField(
        Judge, blank=True, verbose_name=_("judges"), through=Bench
    )
    lower_court_judges = models.ManyToManyField(
        Judge,
        through=LowerBench,
        blank=True,
        verbose_name=_("lower court judges"),
        related_name="lower_court_judgments",
    )
    attorneys = models.ManyToManyField(
        Attorney, blank=True, verbose_name=_("attorneys")
    )
    outcomes = models.ManyToManyField(
        Outcome,
        blank=True,
        related_name="judgments",
    )
    # Summary fields
    case_summary = models.TextField(_("case summary"), null=True, blank=True)
    flynote = models.TextField(_("flynote"), null=True, blank=True)
    order = models.TextField(_("order"), null=True, blank=True)
    case_summary_public = models.BooleanField(
        _("case summary public"),
        default=False,
        help_text=_(
            "Always show the case summary publicly, even when generated by AI."
        ),
    )
    blurb = models.CharField(
        _("blurb"),
        max_length=4096,
        null=True,
        blank=True,
        help_text=_("A quick summary of the judgment, for use in listings"),
    )
    issues = models.JSONField(
        _("issues"),
        null=True,
        blank=True,
        help_text=_("A list of issues that the judgment addresses"),
    )
    held = models.JSONField(
        _("held"),
        null=True,
        blank=True,
        help_text=_("The main findings of the judgment"),
    )
    summary_ai_generated = models.BooleanField(
        _("summary AI generated"),
        default=False,
        help_text=_("Was this summary generated by an AI?"),
    )
    summary_generated_at = models.DateTimeField(
        _("summary generated at"),
        null=True,
        blank=True,
        help_text=_("When the AI summary was generated"),
    )
    summary_trace_id = models.CharField(
        _("summary trace ID"),
        max_length=1024,
        null=True,
        blank=True,
        help_text=_("The trace ID for the AI summary generation"),
    )
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

    auto_assign_details = models.BooleanField(
        _("Auto-assign details"),
        help_text=_("Whether or not the system should assign the details"),
        default=True,
    )

    must_be_anonymised = models.BooleanField(
        _("Must be anonymised"),
        help_text=_("Must this judgment be anonymised?"),
        default=False,
    )
    anonymised = models.BooleanField(
        _("Anonymised"),
        help_text=_("Has the judgment been anonymised?"),
        default=False,
    )

    CITATION_DATE_FORMAT = "(j F Y)"

    MNC_FORMAT = "[{year}] {author} {serial}"
    """ Format string to use for building short MNCs. """

    frbr_uri_doctypes = ["judgment"]

    default_nature = ("judgment", "Judgment")

    class Meta(CoreDocument.Meta):
        ordering = ["title"]
        verbose_name = _("judgment")
        verbose_name_plural = _("judgments")
        permissions = [("api_judgment", "API judgment access")]

    def __str__(self):
        return self.title

    @property
    def case_duration(self):
        # judgment_date__year minus filing_year
        if self.date and self.filing_year:
            return self.date.year - self.filing_year
        return None

    @cached_property
    def linked_flynotes(self):
        if not self.flynote:
            return []

        # Import lazily so the model does not take a hard import dependency on the
        # analysis module at import time.
        from peachjam.analysis.flynotes import FlynoteParser

        parser = FlynoteParser()
        linked_nodes_by_path = {}
        for judgment_flynote in self.flynotes.select_related("flynote"):
            flynote = judgment_flynote.flynote
            nodes = [*flynote.get_ancestors(), flynote]
            linked_nodes_by_path[tuple(node.name for node in nodes)] = nodes

        linked_lines = []
        text = parser.clean(self.flynote)
        if not text:
            return linked_lines

        for line in parser.normalise_multiline_text(text).splitlines():
            items = []
            for path in parser.parse(line):
                nodes = linked_nodes_by_path.get(tuple(path))
                if nodes:
                    items.append({"flynote": nodes[-1], "nodes": nodes})
            if items:
                linked_lines.append(items)

        return linked_lines

    def assign_mnc(self):
        """Assign an MNC to this judgment, if one hasn't already been assigned or if details have changed."""
        if self.date and self.court_id:
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
            date__year=self.date.year, court_id=self.court_id
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
        if self.auto_assign_details:
            self.frbr_uri_doctype = "judgment"
            self.frbr_uri_actor = self.court.code.lower() if self.court_id else None
            self.frbr_uri_date = str(self.date.year) if self.date else ""
            self.frbr_uri_number = str(self.serial_number) if self.serial_number else ""
        return super().generate_work_frbr_uri()

    def clean(self):
        if self.auto_assign_details:
            self.assign_mnc()
        self.flynote = DocumentContent.clean_html_field(self.flynote)
        self.case_summary = DocumentContent.clean_html_field(self.case_summary)
        self.order = DocumentContent.clean_html_field(self.order)
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

        # can't lookup foreign keys without being saved
        if self.pk:
            case_number = "; ".join(n.string for n in self.case_numbers.all())
            if case_number:
                parts.append("(" + case_number + ")")

        if self.mnc:
            parts.append(self.mnc)

        if self.date:
            with lang_override(self.language.iso_639_1):
                parts.append(format_date(self.date, self.CITATION_DATE_FORMAT))

        if self.case_action:
            parts.append("(" + self.case_action.name + ")")

        self.title = " ".join(parts)
        self.citation = self.title

    def pre_save(self):
        # ensure registry aligns to the court
        if self.registry:
            self.court = self.registry.court

        if self.court_id:
            court = self.court
            if court.country:
                self.jurisdiction = court.country
                self.locality = court.locality

        self.doc_type = "judgment"
        if self.auto_assign_details:
            self.assign_mnc()
            self.assign_title()

        # enforce anonymisation
        if self.must_be_anonymised and not self.anonymised:
            self.published = False

        super().pre_save()

    def ensure_anonymised_source_file(self):
        """If this judgment is anonymised but its source file isn't, then queue up a task to generate a PDF
        from the anonymised file."""
        doc_content = self.get_or_create_document_content()
        if self.anonymised:
            if (
                doc_content
                and doc_content.content_html
                and not doc_content.content_html_is_akn
            ):
                if (
                    not hasattr(self, "source_file")
                    or not self.source_file.file_is_anonymised
                ):
                    # there is no source file, or it is not anonymised
                    create_anonymised_source_file_pdf(
                        self.pk, creator=self, schedule=60
                    )

        elif hasattr(self, "source_file") and self.source_file.anonymised_file_as_pdf:
            # we're not anonymised, but an anonymised source file exists - delete it
            try:
                self.source_file.anonymised_file_as_pdf.delete(False)
            except Exception as e:
                log.warning(
                    f"Ignoring error while deleting {self.source_file.anonymised_file_as_pdf}",
                    exc_info=e,
                )
            self.source_file.anonymised_file_as_pdf = None
            self.source_file.save()

    def create_anonymised_source_file_pdf(self):
        """Create an anonymised source file from the HTML of this judgment. If there is already a source file,
        store this new one as the anonymised pdf. Otherwise, create a new source file using this PDF and set
        the anonymised flag."""
        doc_content = self.get_or_create_document_content()
        if (
            self.anonymised
            and doc_content
            and doc_content.content_html
            and not doc_content.content_html_is_akn
        ):
            pdf = self.convert_html_to_pdf()
            f = File(pdf, name=f"{slugify(self.case_name)}.pdf")

            try:
                self.source_file.anonymised_file_as_pdf = f
                self.source_file.save()
            except SourceFile.DoesNotExist:
                # create a new source file with this PDF as the main file, and the anonymised flag set.
                # there's a small chance of a race condition here, the task will just be retried
                SourceFile.objects.create(
                    document=self,
                    file=f,
                    mimetype="application/pdf",
                    file_is_anonymised=True,
                )

    @on_attribute_changed(
        AFTER_SAVE,
        ["must_be_anonymised", "anonymised"],
        ["blurb", "case_summary", "flynote", "held", "issues", "order"],
    )
    def potentially_generate_summary(self):
        if self.should_have_summary():
            generate_judgment_summary(self.pk)

    def should_have_summary(self):
        return (
            not self.case_summary  # No summary at all
            or self.summary_ai_generated  # Summary exists but is AI-generated
        ) and (
            not self.must_be_anonymised or self.anonymised  # Anonymization OK
        )

    def generate_summary(self):
        """Generate an AI summary for this judgment."""
        if not self.should_have_summary():
            log.warning(
                f"Judgment {self} does not meet criteria for summary generation, skipping."
            )
            return

        summariser = JudgmentSummariser()
        if not summariser.enabled():
            log.warning(
                "Summariser service is not enabled, skipping AI summary generation."
            )
            return

        try:
            summary = summariser.summarise_judgment(self)
            flynote_length = len((summary.flynote or "").strip())
            if 0 < flynote_length <= 20:
                log.warning(
                    "Flynote for judgment %s is suspiciously short (%s chars); retrying summary generation.",
                    self.pk,
                    flynote_length,
                )
                summary = summariser.summarise_judgment(self)
            if not summary.summary:
                log.warning(f"No summary found in response {self.pk}, skipping.")
                return
            self.blurb = summary.blurb
            self.case_summary = summary.summary
            self.flynote = summary.flynote
            self.held = summary.held
            self.issues = summary.issues
            self.order = summary.order
            self.summary_ai_generated = True
            self.save()
        except Exception as e:
            log.error(f"Error generating AI summary for judgment {self.pk}", exc_info=e)


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


class CaseHistory(models.Model):
    judgment_work = models.ForeignKey(
        "peachjam.Work",
        related_name="case_histories",
        on_delete=models.CASCADE,
        verbose_name=_("judgment work"),
    )
    case_number = models.CharField(
        _("case number"), max_length=1024, null=True, blank=True
    )
    historical_judgment_work = models.ForeignKey(
        "peachjam.Work",
        related_name="incoming_case_histories",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("historical judgment work"),
    )
    outcome = models.ForeignKey(
        Outcome,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("outcome"),
    )
    judges = models.ManyToManyField(Judge, verbose_name=_("judges"), blank=True)
    court = models.ForeignKey(
        Court, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("court")
    )
    date = models.DateField(_("date"), null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = _("case history")
        verbose_name_plural = _("case histories")

    def __str__(self):
        if self.judgment_work:
            return f"{self.judgment_work}"
        elif self.case_number:
            return f"{self.case_number}"
        return _("Case history")


class CauseList(CoreDocument):

    decorator = CauseListDecorator()

    frbr_uri_doctypes = ["doc"]
    default_nature = ("causelist", "Cause list")
    court = models.ForeignKey(
        Court,
        on_delete=models.PROTECT,
        null=True,
        verbose_name=_("court"),
        related_name="causelists",
    )
    registry = models.ForeignKey(
        CourtRegistry,
        on_delete=models.PROTECT,
        null=True,
        related_name="causelists",
        blank=True,
    )
    division = models.ForeignKey(
        CourtDivision,
        on_delete=models.PROTECT,
        null=True,
        related_name="causelists",
        blank=True,
    )
    judges = models.ManyToManyField(Judge, blank=True, verbose_name=_("judges"))
    end_date = models.DateField(_("end date"), null=True, blank=True)

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.doc_type = "causelist"
        super().pre_save()


class Replacement(models.Model):
    """A replacement made for anonymisation in a Judgment. Part of the judgment anonymiser app."""

    document = models.ForeignKey(
        "Judgment", on_delete=models.CASCADE, related_name="replacements"
    )
    old_text = models.TextField()
    new_text = models.TextField()
    target = models.JSONField()

    def __str__(self):
        return f"{self.old_text} -> {self.new_text}"


class OffenceCategory(models.Model):
    slug = models.SlugField(_("slug"), unique=True, blank=True)
    name = models.CharField(_("name"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("offence category")
        verbose_name_plural = _("offence categories")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class OffenceTag(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("offence tag")
        verbose_name_plural = _("offence tags")

    def __str__(self):
        return self.name


class CaseTag(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("case tag")
        verbose_name_plural = _("case tags")

    def __str__(self):
        return self.name


class OffenceGrouping(models.Model):
    work = models.ForeignKey(
        "peachjam.Work",
        on_delete=models.PROTECT,
        related_name="offence_groupings",
        verbose_name=_("work"),
        help_text=_("The Work that defines this offence grouping."),
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name=_("parent"),
    )
    kind = models.CharField(_("kind"), max_length=50)
    label = models.CharField(_("label"), max_length=255)
    number = models.CharField(_("number"), max_length=100, blank=True, default="")
    title = models.CharField(_("title"), max_length=1024, blank=True, default="")
    provision_eid = models.CharField(
        _("provision EID"),
        max_length=255,
        blank=True,
        default="",
        help_text=_("AKN element id / EID for the grouping within the work."),
    )
    order = models.IntegerField(_("order"), default=0)

    class Meta:
        ordering = ("work_id", "parent_id", "order", "id")
        verbose_name = _("offence grouping")
        verbose_name_plural = _("offence groupings")
        constraints = [
            models.UniqueConstraint(
                fields=("work", "provision_eid"),
                condition=~models.Q(provision_eid=""),
                name="unique_offencegrouping_work_provision_eid",
            )
        ]
        indexes = [
            models.Index(fields=("kind",), name="offence_grouping_kind_idx"),
            models.Index(
                fields=("work", "kind"), name="offence_grouping_work_kind_idx"
            ),
        ]

    def __str__(self):
        if self.title:
            return f"{self.label}: {self.title}"
        return self.label

    def clean(self):
        super().clean()
        if self.parent and self.parent.work_id != self.work_id:
            raise ValidationError(
                {"parent": _("Parent grouping must belong to the same work.")}
            )


class Offence(models.Model):
    work = models.ForeignKey(
        "peachjam.Work",
        on_delete=models.PROTECT,
        related_name="offences",
        verbose_name=_("work"),
        help_text=_(
            "The Work for the code (e.g., Penal Code) that defines this offence."
        ),
    )
    provision_eid = models.CharField(
        _("provision EID"),
        max_length=2048,
        help_text=_(
            "AKN element id / EID for the provision within the code (e.g., 'sec_296')."
        ),
    )
    code = models.CharField(
        _("offence code"),
        max_length=2048,
        help_text=_(
            "Internal offence code / short identifier (often from the code or a local convention)."
        ),
    )
    grouping = models.ForeignKey(
        "OffenceGrouping",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="offences",
        verbose_name=_("grouping"),
    )
    title = models.CharField(_("title"), max_length=4096)
    description = models.TextField(_("description"), blank=True)
    categories = models.ManyToManyField(
        "OffenceCategory",
        blank=True,
        related_name="offences",
        verbose_name=_("categories"),
    )
    tags = models.ManyToManyField(
        "OffenceTag",
        blank=True,
        related_name="offences",
        verbose_name=_("tags"),
    )
    elements = ArrayField(
        base_field=models.CharField(max_length=4096),
        default=list,
        blank=True,
        help_text=_("List of offence elements (actus reus, mens rea, etc.)."),
    )
    penalty = models.TextField(
        _("recommended penalty"),
        blank=True,
        help_text=_("Human-readable recommended/typical penalty guidance."),
    )

    class Meta:
        ordering = ("title",)
        constraints = [
            models.UniqueConstraint(
                fields=("work", "provision_eid"),
                name="unique_offence_work_provision_eid",
            )
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.grouping and self.grouping.work_id != self.work_id:
            raise ValidationError(
                {"grouping": _("Grouping must belong to the same work.")}
            )


class JudgmentOffence(models.Model):
    judgment = models.ForeignKey(
        "Judgment",
        on_delete=models.CASCADE,
        related_name="judgment_offence",
        verbose_name=_("judgment"),
    )
    offence = models.ForeignKey(
        Offence,
        on_delete=models.PROTECT,
        related_name="judgment_offence",
        verbose_name=_("judgments"),
    )
    tags = models.ManyToManyField(
        "CaseTag",
        blank=True,
        related_name="judgment_offences",
        verbose_name=_("case tags"),
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("judgment", "offence"),
                name="unique_judgment_offence_judgment_offence",
            )
        ]

    def __str__(self):
        return f"JudgmentOffence {self.offence} - {self.judgment}"


class Sentence(models.Model):
    class SentenceType(models.TextChoices):
        IMPRISONMENT = "imprisonment", _("Imprisonment")
        FINE = "fine", _("Fine")
        PROBATION = "probation", _("Probation")

    judgment = models.ForeignKey(
        Judgment,
        on_delete=models.CASCADE,
        related_name="sentences",
        verbose_name=_("offences"),
    )

    offence = models.ForeignKey(
        JudgmentOffence,
        on_delete=models.CASCADE,
        related_name="sentences",
        verbose_name=_("offences"),
        null=True,
        blank=True,
    )
    sentence_type = models.CharField(
        _("sentence type"),
        max_length=32,
        choices=SentenceType.choices,
    )

    mandatory_minimum = models.BooleanField(
        _("mandatory minimum"),
        null=True,
        blank=True,
        help_text=_("True if the sentence reflects a mandatory minimum."),
    )

    duration_months = models.PositiveIntegerField(
        _("duration (months)"),
        null=True,
        blank=True,
        help_text=_("Imprisonment/probation duration in months, if applicable."),
    )
    suspended = models.BooleanField(
        _("suspended"),
        default=False,
        help_text=_("True if the sentence is suspended (fully or partially)."),
    )
    fine_amount = models.PositiveIntegerField(
        _("fine amount"),
        null=True,
        blank=True,
        help_text=_("Fine amount"),
    )

    class Meta:
        ordering = ("pk",)

    def __str__(self):
        return f"{self.get_sentence_type_display()} for {self.offence}"
