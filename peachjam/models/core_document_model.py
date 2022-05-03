import os

import magic
from cobalt import FrbrUri
from cobalt.akn import datestring
from countries_plus.models import Country
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from languages_plus.models import Language


class Locality(models.Model):
    name = models.CharField(max_length=255, null=False)
    jurisdiction = models.ForeignKey(Country, on_delete=models.PROTECT)
    code = models.CharField(max_length=20, null=False)

    class Meta:
        verbose_name_plural = "localities"
        ordering = ["name"]
        unique_together = ["name", "jurisdiction"]

    def __str__(self):
        return f"{self.name}"


class CoreDocument(models.Model):
    DOC_TYPE_CHOICES = (
        ("core_document", "Core Document"),
        ("legislation", "Legislation"),
        ("generic_document", "Generic Document"),
        ("legal_instrument", "Legal Instrument"),
        ("judgment", "Judgment"),
    )

    doc_type = models.CharField(
        max_length=255,
        choices=DOC_TYPE_CHOICES,
        default="core_document",
        null=False,
        blank=False,
    )
    title = models.CharField(max_length=1024, null=False, blank=False)
    date = models.DateField(null=False, blank=False)
    source_url = models.URLField(max_length=2048, null=True, blank=True)
    citation = models.CharField(max_length=1024, null=True, blank=True)
    content_html = models.TextField(null=True, blank=True)
    content_html_is_akn = models.BooleanField(default=False)
    toc_json = models.JSONField(null=True, blank=True)
    language = models.ForeignKey(
        Language, on_delete=models.PROTECT, null=False, blank=False
    )
    jurisdiction = models.ForeignKey(
        Country, on_delete=models.PROTECT, null=False, blank=False
    )
    locality = models.ForeignKey(
        Locality, on_delete=models.PROTECT, null=True, blank=True
    )
    expression_frbr_uri = models.CharField(
        max_length=1024, null=False, blank=False, unique=True
    )
    work_frbr_uri = models.CharField(max_length=1024, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["doc_type", "title"]

    def __str__(self):
        return f"{self.doc_type} - {self.title}"

    def get_all_fields(self):
        return self._meta.get_fields()

    def get_all_values(self):
        return serializers.serialize("python", [self])[0]["fields"]

    def get_absolute_url(self):
        return reverse(f"{self.doc_type}_detail", kwargs={"pk": self.pk})

    def clean(self):
        try:
            FrbrUri.parse(self.work_frbr_uri)
        except ValueError:
            raise ValidationError({"work_frbr_uri": "Invalid FRBR URI."})

    def generate_expression_frbr_uri(self):
        frbr_uri = FrbrUri.parse(self.work_frbr_uri)
        frbr_uri.expression_date = f"@{datestring(self.date)}"
        frbr_uri.language = self.language.iso_639_3
        return frbr_uri.expression_uri()

    def save(self, *args, **kwargs):
        if not self.expression_frbr_uri:
            self.expression_frbr_uri = self.generate_expression_frbr_uri()
        return super().save(*args, **kwargs)


def file_location(instance, filename):
    if not instance.document.pk:
        raise ValueError("Document must be saved before file can be attached")
    doc_type = instance.document.doc_type
    pk = instance.document.pk
    folder = instance.SAVE_FOLDER
    filename = os.path.basename(filename)
    return f"media/{doc_type}/{pk}/{folder}/{filename}"


class AttachmentAbstractModel(models.Model):
    filename = models.CharField(max_length=1024, null=False, blank=False)
    mimetype = models.CharField(max_length=1024, null=False, blank=False)

    def __str__(self):
        return f"{self.filename}"

    class Meta:
        abstract = True


class Image(AttachmentAbstractModel):
    SAVE_FOLDER = "images"

    document = models.ForeignKey(
        CoreDocument, related_name="images", on_delete=models.PROTECT
    )
    file = models.ImageField(upload_to=file_location, max_length=1024)


class SourceFile(AttachmentAbstractModel):
    SAVE_FOLDER = "source_file"

    document = models.OneToOneField(
        CoreDocument, related_name="source_file", on_delete=models.PROTECT
    )
    file = models.FileField(upload_to=file_location, max_length=1024)

    def save(self, *args, **kwargs):
        self.filename = self.file.name
        if not self.mimetype:
            self.mimetype = magic.from_buffer(self.file.read(), mime=True)
        return super().save(*args, **kwargs)
