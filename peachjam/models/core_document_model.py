import os
import re

import magic
from cobalt import FrbrUri
from cobalt.akn import datestring
from countries_plus.models import Country
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.utils.functional import cached_property
from docpipe.pipeline import PipelineContext
from docpipe.soffice import soffice_convert
from languages_plus.models import Language

from peachjam.frbr_uri import (
    FRBR_URI_DOCTYPE_CHOICES,
    FRBR_URI_DOCTYPES,
    validate_frbr_uri_component,
    validate_frbr_uri_date,
)
from peachjam.pipelines import DOC_MIMETYPES, word_pipeline


class Locality(models.Model):
    name = models.CharField(max_length=255, null=False)
    jurisdiction = models.ForeignKey(Country, on_delete=models.PROTECT)
    code = models.CharField(max_length=20, null=False)

    class Meta:
        verbose_name_plural = "localities"
        ordering = ["name"]
        unique_together = ["name", "jurisdiction"]

    def place_code(self):
        return f"{self.jurisdiction.pk.lower()}-{self.code}"

    def __str__(self):
        return self.name


class Work(models.Model):
    frbr_uri = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    title = models.CharField(max_length=1024, null=False, blank=False)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.frbr_uri} - {self.title}"


class CoreDocumentQuerySet(models.QuerySet):
    def latest_expression(self):
        """Select only the most recent expression for documents with the same frbr_uri."""
        return self.distinct("work_frbr_uri").order_by("work_frbr_uri", "-date")


class CoreDocument(models.Model):
    DOC_TYPE_CHOICES = (
        ("core_document", "Core Document"),
        ("legislation", "Legislation"),
        ("generic_document", "Generic Document"),
        ("legal_instrument", "Legal Instrument"),
        ("judgment", "Judgment"),
    )

    objects = CoreDocumentQuerySet.as_manager()

    work = models.ForeignKey(
        Work, null=False, on_delete=models.PROTECT, related_name="documents"
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

    work_frbr_uri = models.CharField(max_length=1024, null=False, blank=False)

    # components used to build the work FRBR URI
    frbr_uri_doctype = models.CharField(
        max_length=20, choices=FRBR_URI_DOCTYPE_CHOICES, null=False, blank=False
    )
    frbr_uri_subtype = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_frbr_uri_component],
        help_text="Document subtype. Lowercase letters, numbers _ and - only.",
    )
    frbr_uri_actor = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_frbr_uri_component],
        help_text="Originating actor. Lowercase letters, numbers _ and - only.",
    )
    frbr_uri_date = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        validators=[validate_frbr_uri_date],
        help_text="YYYY, YYYY-MM, or YYYY-MM-DD",
    )
    frbr_uri_number = models.CharField(
        max_length=1024,
        null=False,
        blank=False,
        validators=[validate_frbr_uri_component],
        help_text="Unique number or short title identifying this work. Lowercase letters, numbers _ and - only.",
    )

    expression_frbr_uri = models.CharField(
        max_length=1024, null=False, blank=False, unique=True
    )
    """This is derived from the work_frbr_uri, language and date."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # options for the FRBR URI doctypes
    frbr_uri_doctypes = FRBR_URI_DOCTYPES

    class Meta:
        ordering = ["doc_type", "title"]

    def __str__(self):
        return f"{self.doc_type} - {self.title}"

    def get_all_fields(self):
        return self._meta.get_fields()

    def get_absolute_url(self):
        return self.expression_frbr_uri

    @property
    def get_taxonomies(self):
        return list(
            self.taxonomies.distinct("topic").values_list("topic__name", flat=True)
        )

    @property
    def year(self):
        return self.date.year

    def clean(self):
        super().clean()
        frbr_uri = self.generate_work_frbr_uri()
        try:
            FrbrUri.parse(frbr_uri)
        except ValueError:
            raise ValidationError("Invalid FRBR URI: " + frbr_uri)

        self.assign_frbr_uri()
        expression_frbr_uri = self.generate_expression_frbr_uri()
        if (
            self.__class__.objects.filter(expression_frbr_uri=expression_frbr_uri)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                "Document with this Expression FRBR URI already exists!"
                + expression_frbr_uri
            )

    def generate_expression_frbr_uri(self):
        frbr_uri = FrbrUri.parse(self.work_frbr_uri)
        frbr_uri.expression_date = f"@{datestring(self.date)}"
        frbr_uri.language = self.language.iso_639_3
        return frbr_uri.expression_uri()

    def expression_uri(self):
        """Parsed form of expression_frbr_uri."""
        return FrbrUri.parse(self.expression_frbr_uri)

    def assign_frbr_uri(self):
        """Generate and store a Work FRBR URI for this document."""
        self.work_frbr_uri = self.generate_work_frbr_uri()

    def generate_work_frbr_uri(self):
        """Generate a work FRBR URI for this document."""
        if not self.frbr_uri_date and self.date:
            self.frbr_uri_date = self.date.strftime("%Y-%m-%d")

        frbr_uri = FrbrUri(
            self.jurisdiction.iso.lower() if hasattr(self, "jurisdiction") else "",
            self.locality.code if self.locality else None,
            self.frbr_uri_doctype,
            # TODO: this works around a bug that FrbrUri cannot differentiate between an actor and a subtype
            self.frbr_uri_subtype or self.frbr_uri_actor,
            self.frbr_uri_actor if self.frbr_uri_subtype else None,
            self.frbr_uri_date,
            self.frbr_uri_number,
        )
        return frbr_uri.work_uri(work_component=False)

    def save(self, *args, **kwargs):
        self.assign_frbr_uri()
        self.expression_frbr_uri = self.generate_expression_frbr_uri()

        # ensure a matching work exists
        if not hasattr(self, "work") or self.work.frbr_uri != self.work_frbr_uri:
            self.work, _ = Work.objects.get_or_create(
                frbr_uri=self.work_frbr_uri,
                defaults={
                    "title": self.title,
                },
            )

        # keep work title in sync with English documents
        if self.language.iso_639_3 == "eng" and self.work.title != self.title:
            self.work.title = self.title
            self.work.save()

        return super().save(*args, **kwargs)

    @cached_property
    def relationships_as_subject(self):
        """Returns a list of relationships where this work is the subject."""
        from peachjam.models import Relationship

        return Relationship.for_subject_document(self).prefetch_related(
            "subject_work", "subject_work__documents"
        )

    @cached_property
    def relationships_as_object(self):
        """Returns a list of relationships where this work is the subject."""
        from peachjam.models import Relationship

        return Relationship.for_object_document(self).prefetch_related(
            "object_work", "object_work__documents"
        )

    def extract_citations(self):
        """Run citation extraction on this document. If the document has content_html,
        extraction will be run on that. Otherwise, if the document as a PDF source file,
        extraction will be run on that.
        """
        from peachjam.analysis.citations import citation_analyser
        from peachjam.models.citations import CitationLink

        # delete existing citation links
        CitationLink.objects.filter(document=self).delete()
        return citation_analyser.extract_citations(self)

    def extract_content_from_source_file(self):
        """Re-extract content from DOCX source files, overwriting anything in content_html and associated images.

        This requires that the document has already been saved, in order to associate image attachments.
        """
        if (
            not self.content_html_is_akn
            and hasattr(self, "source_file")
            and self.source_file.mimetype in DOC_MIMETYPES
        ):
            context = PipelineContext(word_pipeline)
            context.source_file = self.source_file.file
            word_pipeline(context)
            self.content_html = context.html_text

            for img in self.images.all():
                img.delete()

            for attachment in context.attachments:
                if attachment.content_type.startswith("image/"):
                    img = Image.from_docpipe_attachment(attachment)
                    img.document = self
                    img.save()
                    self.images.add(img)

            return True


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
    size = models.BigIntegerField(default=0)

    def __str__(self):
        return f"{self.filename}"

    class Meta:
        abstract = True


class Image(AttachmentAbstractModel):
    SAVE_FOLDER = "images"

    document = models.ForeignKey(
        CoreDocument, related_name="images", on_delete=models.CASCADE
    )
    file = models.ImageField(upload_to=file_location, max_length=1024)

    @classmethod
    def from_docpipe_attachment(cls, attachment):
        f = File(attachment.file, name=attachment.filename)
        return Image(
            filename=attachment.filename,
            mimetype=attachment.content_type,
            size=f.size,
            file=f,
        )


class SourceFile(AttachmentAbstractModel):
    SAVE_FOLDER = "source_file"

    document = models.OneToOneField(
        CoreDocument, related_name="source_file", on_delete=models.CASCADE
    )
    file = models.FileField(upload_to=file_location, max_length=1024)

    def save(self, *args, **kwargs):
        # store this so that we don't have to calculate
        self.size = self.file.size
        self.filename = self.file.name
        if not self.mimetype:
            self.mimetype = magic.from_buffer(self.file.read(), mime=True)
        return super().save(*args, **kwargs)

    def as_pdf(self):
        if self.filename.endswith(".pdf"):
            return self.file

        # convert with soffice
        suffix = os.path.splitext(self.filename)[1].replace(".", "")
        return soffice_convert(self.file, suffix, "pdf")[0]

    def filename_extension(self):
        return os.path.splitext(self.filename)[1][1:]

    def filename_for_download(self):
        """Return a generated filename appropriate for use when downloading this source file."""
        ext = os.path.splitext(self.filename)[1]
        title = re.sub(r"[^a-zA-Z0-9() ]", "", self.document.title)
        return title + ext
