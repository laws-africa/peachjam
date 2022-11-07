from django.db import models
from django.db.models import Max

from peachjam.models import CoreDocument


class Judge(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class MatterType(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class CourtClass(models.Model):
    name = models.CharField(max_length=100, null=False, unique=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Court classes"

    def __str__(self):
        return self.name


class Court(models.Model):
    name = models.CharField(max_length=255, null=False, unique=True)
    code = models.SlugField(max_length=255, null=False, unique=True)
    court_class = models.ForeignKey(
        CourtClass, related_name="courts", on_delete=models.PROTECT, null=True
    )

    def __str__(self):
        return self.name


class Judgment(CoreDocument):
    court = models.ForeignKey(Court, on_delete=models.PROTECT, null=True)
    judges = models.ManyToManyField(Judge, blank=True)
    headnote_holding = models.TextField(null=True, blank=True)
    additional_citations = models.TextField(null=True, blank=True)
    flynote = models.TextField(null=True, blank=True)
    case_name = models.CharField(
        max_length=4096,
        help_text="Party names for use in title",
        null=False,
        blank=False,
    )
    serial_number = models.IntegerField(
        # TODO: this must be changed to True
        null=False,
        help_text="Serial number for MNC, unique for a year and an author.",
    )
    serial_number_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Specific MNC serial number assigned by the court.",
    )

    mnc = models.CharField(
        max_length=4096, help_text="Media neutral citation", null=False, blank=False
    )
    hearing_date = models.DateField(null=True, blank=True)

    CITATION_DATE_FORMAT = "(%d %B %Y)"

    MNC_FORMAT = "[{year}] {author} {serial}"
    """ Format string to use for building short MNCs. """

    frbr_uri_doctypes = ["judgment"]

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def assign_mnc(self):
        """Assign an MNC to this judgment, if one hasn't already been assigned or if details have changed."""
        if self.date and hasattr(self, "court"):
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
        self.frbr_uri_actor = (
            self.court.code.lower() if hasattr(self, "court") else None
        )
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
            parts.append(self.date.strftime(self.CITATION_DATE_FORMAT))

        self.title = " ".join(parts)
        self.citation = self.title

    def judges_string(self):
        return ", ".join(j.name for j in self.judges.all())

    def save(self, *args, **kwargs):
        self.doc_type = "judgment"
        self.assign_mnc()
        self.assign_title()
        return super().save(*args, **kwargs)


class CaseNumber(models.Model):
    string_override = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        help_text="Override for full case number string",
    )
    string = models.CharField(max_length=1024, null=True, blank=True)
    number = models.PositiveIntegerField(null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    matter_type = models.ForeignKey(
        MatterType, on_delete=models.PROTECT, null=True, blank=True
    )

    document = models.ForeignKey(
        Judgment, related_name="case_numbers", on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.string)

    def get_case_number_string(self):
        if self.string_override:
            return self.string_override
        return f"{self.matter_type or ''} {self.number} of {self.year}".strip()

    def save(self, *args, **kwargs):
        self.string = self.get_case_number_string()
        return super().save(*args, **kwargs)
