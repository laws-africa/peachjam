from django.db import models
from django.db.models import Max

from peachjam.models import CoreDocument, file_location
from peachjam.models.author import Author


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


class Judgment(CoreDocument):
    author = models.ForeignKey(Author, on_delete=models.PROTECT)
    judges = models.ManyToManyField(Judge, blank=True)
    headnote_holding = models.TextField(blank=True)
    additional_citations = models.TextField(blank=True)
    flynote = models.TextField(blank=True)
    case_name = models.CharField(
        max_length=4096,
        help_text="Party names for use in title",
        null=False,
        blank=False,
    )
    serial_number = models.IntegerField(
        null=False, help_text="Serial number for MNC, unique for a year and an author."
    )
    mnc = models.CharField(
        max_length=4096, help_text="Media neutral citation", null=False, blank=False
    )

    CITATION_DATE_FORMAT = "(%d %B %Y)"

    MNC_FORMAT = "[{year}] {author} {serial}"
    """ Format string to use for building short MNCs. """

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def assign_mnc(self):
        """Assign an MNC to this judgment, if one hasn't already been assigned."""
        if self.mnc != self.generate_citation():
            self.serial_number = self.generate_serial_number()
            self.mnc = self.generate_citation()

        # when assigning the MNC, also ensure the FRBR URI is correct, since they are directly linked
        self.assign_frbr_uri()

    def generate_serial_number(self):
        """Generate a candidate serial number for this decision, based on the delivery year and court."""
        # use select_for_update to lock the touched rows, to avoid a race condition and duplicate serial numbers
        query = Judgment.objects.select_for_update().filter(
            date__year=self.date.year, author=self.author
        )
        if self.pk:
            query = query.exclude(pk=self.pk)

        num = query.aggregate(num=Max("serial_number"))
        return (num["num"] or 0) + 1

    def generate_citation(self):
        return self.MNC_FORMAT.format(
            year=self.date.year, author=self.author.code, serial=self.serial_number
        )

    def assign_frbr_uri(self):
        self.work_frbr_uri = self.generate_work_frbr_uri()

    def generate_work_frbr_uri(self):
        """Generate a work FRBR URI based on the MNC data."""
        place = [self.jurisdiction.iso.lower()]
        if self.locality:
            place.append(self.locality.code)
        place = "-".join(place).lower()
        return f"/akn/{place}/judgment/{self.author.code.lower()}/{self.date.year}/{self.serial_number}"

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

    def save(self, *args, **kwargs):
        self.doc_type = "judgment"
        self.assign_mnc()
        # TODO: only do this from the form?
        self.assign_title()
        return super().save(*args, **kwargs)


class CaseNumber(models.Model):
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
        return f"{self.matter_type or ''} {self.number} of {self.year}".strip()

    def save(self, *args, **kwargs):
        self.string = self.get_case_number_string()
        return super().save(*args, **kwargs)


class JudgmentMediaSummaryFile(models.Model):
    SAVE_FOLDER = "media_summary_files"

    document = models.ForeignKey(
        Judgment, related_name="media_summaries", on_delete=models.PROTECT
    )
    file = models.FileField(upload_to=file_location)
    size = models.IntegerField()
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["document", "filename"]

    def __str__(self):
        return f"{self.filename}"
