from countries_plus.models import Country
from django.db import models

from peachjam.models import CoreDocument, file_location


class Court(models.Model):
    name = models.CharField(max_length=255, null=False)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    code = models.CharField(max_length=255, null=False)

    class Meta:
        ordering = ["name"]
        unique_together = ["name", "country"]

    def __str__(self):
        return f"{self.name}"


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
    court = models.ForeignKey(Court, on_delete=models.PROTECT, null=True, blank=True)
    judges = models.ManyToManyField(Judge, blank=True)
    headnote_holding = models.TextField(blank=True)
    additional_citations = models.TextField(blank=True)
    flynote = models.TextField(blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "judgment"
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
        return f"{self.string}"

    def get_case_number_string(self):
        return f"{self.matter_type} {self.number} of {self.year}"

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
