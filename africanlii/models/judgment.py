import os
from django.db import models
from django.urls import reverse
from countries_plus.models import Country
from .core_document_model import CoreDocumentModel


class Court(models.Model):
    name = models.CharField(max_length=255, null=False)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'courts'
        ordering = ['name']
        unique_together = ['name', 'country']

    def __str__(self):
        return f'{self.name}'

from django.db import models

class Judge(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class MatterType(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Judgment(CoreDocumentModel):
    case_number_numeric = models.CharField(max_length=1024, null=True, blank=True)
    case_number_year = models.IntegerField(null=True, blank=True)
    case_number_string = models.CharField(max_length=1024, null=True, blank=True)
    matter_type = models.ForeignKey(MatterType, on_delete=models.PROTECT, null=True, blank=True)
    court = models.ForeignKey(Court, on_delete=models.PROTECT, null=True, blank=True)
    judges = models.ManyToManyField(Judge, blank=True)
    headnote_holding = models.TextField(blank=True)
    additional_citations = models.TextField(blank=True)
    flynote = models.TextField(blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.case_number_string = self.get_case_number_string()
        return super().save(*args, **kwargs)

    def get_case_number_string(self):
        return f'{self.matter_type} {self.case_number_numeric} of {self.case_number_year}'

    def get_absolute_url(self):
        return reverse('judgment_detail', args=str(self.id))

def media_summary_file_location(instance, filename):
    return f'media/judgments/{instance.judgment.id}/{os.path.basename(filename)}'

class JudgmentMediaSummaryFile(models.Model):
    judgment = models.ForeignKey(Judgment, related_name='attachments', on_delete=models.PROTECT)
    file = models.FileField(upload_to=media_summary_file_location)
    size = models.IntegerField()
    filename = models.CharField(max_length=255, help_text="Unique attachment filename")
    mime_type = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['filename']
