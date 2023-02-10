import datetime
import os
import re

import magic
from cobalt.akn import datestring
from cobalt.uri import FrbrUri
from countries_plus.models import Country
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from docpipe.pipeline import PipelineContext
from docpipe.soffice import soffice_convert
from languages_plus.models import Language
from lxml import html
from polymorphic.managers import PolymorphicManager
from polymorphic.models import PolymorphicModel
from polymorphic.query import PolymorphicQuerySet

from peachjam.frbr_uri import (
    FRBR_URI_DOCTYPE_CHOICES,
    FRBR_URI_DOCTYPES,
    validate_frbr_uri_component,
    validate_frbr_uri_date,
)
from peachjam.models import CitationLink, ExtractedCitation
from peachjam.pipelines import DOC_MIMETYPES, word_pipeline
from peachjam.storage import DynamicStorageFileField


class DocumentNature(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    code = models.SlugField(_("code"), max_length=1024, null=False, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("document nature")
        verbose_name_plural = _("document natures")

    def __str__(self):
        return self.name


class Locality(models.Model):
    name = models.CharField(_("name"), max_length=255, null=False)
    jurisdiction = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name=_("jurisdiction")
    )
    code = models.CharField(_("code"), max_length=20, null=False)

    class Meta:
        verbose_name = _("locality")
        verbose_name_plural = _("localities")
        ordering = ["name"]
        unique_together = ["name", "jurisdiction"]

    def place_code(self):
        return f"{self.jurisdiction.pk.lower()}-{self.code}"

    def __str__(self):
        return self.name


class Work(models.Model):
    frbr_uri = models.CharField(
        _("FRBR URI"), max_length=1024, null=False, blank=False, unique=True
    )
    title = models.CharField(_("title"), max_length=1024, null=False, blank=False)
    languages = ArrayField(
        models.CharField(max_length=3),
        null=False,
        blank=False,
        default=list,
        verbose_name=_("languages"),
    )

    class Meta:
        verbose_name = _("work")
        verbose_name_plural = _("works")
        ordering = ["title"]

    def update_languages(self):
        """Update this work's languages to reflect the distinct languages of its related documents."""
        langs = list(
            CoreDocument.objects.filter(work=self)
            .distinct("language__iso_639_3")
            .values_list("language__iso_639_3", flat=True)
            .order_by("language__iso_639_3")
        )
        if langs != self.languages:
            self.languages = langs
            self.save()

    def update_extracted_citations(self):
        """Update the current work's ExtractedCitations."""
        target_works = Work.objects.filter(
            frbr_uri__in=self.fetch_cited_works_frbr_uris()
        )

        # delete existing extracted citations
        ExtractedCitation.objects.filter(citing_work=self).delete()

        for target_work in target_works:
            ExtractedCitation.objects.get_or_create(
                citing_work=self, target_work=target_work
            )

    def fetch_cited_works_frbr_uris(self):
        """Returns a set of work_frbr_uris,
        taken from CitationLink objects(for PDFs) and all <a href="/akn/..."> embedded HTML links."""
        for doc in self.documents.all():

            work_frbr_uris = set()

            if doc.content_html:
                root = html.fromstring(doc.content_html)
                for a in root.xpath('//a[starts-with(@href, "/akn")]'):
                    try:
                        work_frbr_uris.add(FrbrUri.parse(a.attrib["href"]).work_uri())
                    except ValueError:
                        # ignore malformed FRBR URIs
                        pass
            else:
                for citation_link in CitationLink.objects.filter(document_id=doc.pk):
                    try:
                        work_frbr_uris.add(FrbrUri.parse(citation_link.url).work_uri())
                    except ValueError:
                        # ignore malformed FRBR URIs
                        pass

            # A work does not cite itself
            if self.frbr_uri in work_frbr_uris:
                work_frbr_uris.remove(self.frbr_uri)

            return work_frbr_uris

    def cited_works(self):
        """Shows a list of works cited by the current work."""
        return ExtractedCitation.for_citing_works(self)

    def works_citing_current_work(self):
        """Shows a list of works that cite the current work."""
        return ExtractedCitation.for_target_works(self)

    def __str__(self):
        return f"{self.frbr_uri} - {self.title}"


class CoreDocumentManager(PolymorphicManager):
    def get_queryset(self):
        # defer expensive fields
        return super().get_queryset().defer("content_html", "toc_json")


class CoreDocumentQuerySet(PolymorphicQuerySet):
    def latest_expression(self):
        """Select only the most recent expression for documents with the same frbr_uri."""
        return self.distinct("work_frbr_uri").order_by("work_frbr_uri", "-date")

    def preferred_language(self, language):
        """Return documents whose language match the preferred one,
        or return all docs if there are no documents in the preferred language.
        """
        return self.filter(
            models.Q(language_id__iso_639_3=language)
            | ~models.Q(work__languages__contains=[language])
        )


class CoreDocument(PolymorphicModel):
    DOC_TYPE_CHOICES = (
        ("core_document", "Core Document"),
        ("gazette", "Gazette"),
        ("generic_document", "Generic Document"),
        ("judgment", "Judgment"),
        ("legal_instrument", "Legal Instrument"),
        ("legislation", "Legislation"),
        ("book", "Book"),
        ("journal", "Journal"),
    )

    objects = CoreDocumentManager.from_queryset(CoreDocumentQuerySet)()

    work = models.ForeignKey(
        Work,
        null=False,
        on_delete=models.PROTECT,
        related_name="documents",
        verbose_name=_("work"),
    )
    doc_type = models.CharField(
        _("document type"),
        max_length=255,
        choices=DOC_TYPE_CHOICES,
        default="core_document",
        null=False,
        blank=False,
    )
    title = models.CharField(_("title"), max_length=1024, null=False, blank=False)
    date = models.DateField(_("date"), null=False, blank=False, db_index=True)
    source_url = models.URLField(
        _("source URL"), max_length=2048, null=True, blank=True
    )
    citation = models.CharField(_("citation"), max_length=1024, null=True, blank=True)
    content_html = models.TextField(_("content HTML"), null=True, blank=True)
    content_html_is_akn = models.BooleanField(_("content HTML is AKN"), default=False)
    toc_json = models.JSONField(_("TOC JSON"), null=True, blank=True)
    language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("language"),
    )
    jurisdiction = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("jurisdiction"),
    )
    locality = models.ForeignKey(
        Locality,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("locality"),
    )
    nature = models.ForeignKey(
        DocumentNature,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("nature"),
    )

    work_frbr_uri = models.CharField(
        _("work FRBR URI"), max_length=1024, null=False, blank=False
    )

    # components used to build the work FRBR URI
    frbr_uri_doctype = models.CharField(
        _("FRBR URI doctype"),
        max_length=20,
        choices=FRBR_URI_DOCTYPE_CHOICES,
        null=False,
        blank=False,
    )
    frbr_uri_subtype = models.CharField(
        _("FRBR URI subtype"),
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_frbr_uri_component],
        help_text=_("Document subtype. Lowercase letters, numbers _ and - only."),
    )
    frbr_uri_actor = models.CharField(
        _("FRBR URI actor"),
        max_length=100,
        null=True,
        blank=True,
        validators=[validate_frbr_uri_component],
        help_text=_("Originating actor. Lowercase letters, numbers _ and - only."),
    )
    frbr_uri_date = models.CharField(
        _("FRBR URI date"),
        max_length=10,
        null=False,
        blank=False,
        validators=[validate_frbr_uri_date],
        help_text=_("YYYY, YYYY-MM, or YYYY-MM-DD"),
    )
    frbr_uri_number = models.CharField(
        _("FRBR URI number"),
        max_length=1024,
        null=False,
        blank=False,
        validators=[validate_frbr_uri_component],
        help_text=_(
            "Unique number or short title identifying this work. Lowercase letters, numbers _ and - only."
        ),
    )

    expression_frbr_uri = models.CharField(
        _("expression FRBR URI"), max_length=1024, null=False, blank=False, unique=True
    )
    """This is derived from the work_frbr_uri, language and date."""

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    allow_robots = models.BooleanField(
        _("allow robots"),
        default=True,
        db_index=True,
        help_text=_("Allow this document to be indexed by search engine robots."),
    )

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
    def year(self):
        return self.date.year

    def clean(self):
        super().clean()

        if self.date is None:
            raise ValidationError(_("Invalid Date"))

        if self.date > datetime.date.today():
            raise ValidationError(_("You cannot set a future date for the document"))

        frbr_uri = self.generate_work_frbr_uri()
        try:
            FrbrUri.parse(frbr_uri)
        except ValueError:
            raise ValidationError(_("Invalid FRBR URI: %(uri)s") % {"uri": frbr_uri})

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
        self.frbr_uri_subtype = self.nature.code if self.nature else None

        self.assign_frbr_uri()
        self.expression_frbr_uri = self.generate_expression_frbr_uri()

        # ensure a matching work exists
        if not hasattr(self, "work") or self.work.frbr_uri != self.work_frbr_uri:
            self.work, _ = Work.objects.get_or_create(
                frbr_uri=self.work_frbr_uri,
                defaults={"title": self.title},
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

    def is_most_recent(self):
        """Is this the most recent document for this work?

        Note that there can be multiple most recent documents, all at the same data but in different languages.
        """
        return (
            self.work.documents.filter(language=self.language)
            .order_by("-date")
            .values_list("pk", flat=True)
            .first()
            == self.pk
        )


def file_location(instance, filename):
    if not instance.document.pk:
        raise ValueError("Document must be saved before file can be attached")
    doc_type = instance.document.doc_type
    pk = instance.document.pk
    folder = instance.SAVE_FOLDER
    filename = os.path.basename(filename)
    return f"media/{doc_type}/{pk}/{folder}/{filename}"


class AttachmentAbstractModel(models.Model):
    filename = models.CharField(_("filename"), max_length=1024, null=False, blank=False)
    mimetype = models.CharField(_("mimetype"), max_length=1024, null=False, blank=False)
    size = models.BigIntegerField(_("size"), default=0)
    file = DynamicStorageFileField(_("file"), upload_to=file_location, max_length=1024)

    def __str__(self):
        return f"{self.filename}"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.size = self.file.size
        self.filename = self.file.name

        if not self.mimetype:
            self.mimetype = magic.from_buffer(self.file.read(), mime=True)
        return super().save(*args, **kwargs)


class Image(AttachmentAbstractModel):
    SAVE_FOLDER = "images"

    document = models.ForeignKey(
        CoreDocument,
        related_name="images",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    file = models.ImageField(_("file"), upload_to=file_location, max_length=1024)

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")

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
        CoreDocument,
        related_name="source_file",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    source_url = models.URLField(
        _("source URL"), max_length=2048, null=True, blank=True
    )

    class Meta:
        verbose_name = _("source file")
        verbose_name_plural = _("source files")

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


class AttachedFileNature(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("attached file nature")
        verbose_name_plural = _("attached file natures")

    def __str__(self):
        return self.name


class AttachedFiles(AttachmentAbstractModel):
    SAVE_FOLDER = "attachments"

    document = models.ForeignKey(
        CoreDocument, on_delete=models.CASCADE, verbose_name=_("document")
    )
    nature = models.ForeignKey(
        AttachedFileNature, on_delete=models.CASCADE, verbose_name=_("nature")
    )

    class Meta:
        verbose_name = _("attached file")
        verbose_name_plural = _("attached files")

    def extension(self):
        return os.path.splitext(self.filename)[1].replace(".", "")


class AlternativeName(models.Model):
    document = models.ForeignKey(
        CoreDocument,
        on_delete=models.CASCADE,
        related_name="alternative_names",
        verbose_name=_("document"),
    )
    title = models.CharField(_("title"), max_length=1024, null=False, blank=False)

    class Meta:
        verbose_name = _("alternative name")
        verbose_name_plural = _("alternative names")

    def __str__(self):
        return self.title
