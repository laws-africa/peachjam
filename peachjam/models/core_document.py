import base64
import logging
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass

from cobalt.akn import StructuredDocument, datestring
from cobalt.uri import FrbrUri
from countries_plus.models import Country
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from docpipe.pipeline import PipelineContext
from docpipe.soffice import soffice_convert
from docpipe.xmlutils import unwrap_element
from languages_plus.models import Language
from lxml import etree, html
from lxml.etree import ParserError
from polymorphic.managers import PolymorphicManager
from polymorphic.models import PolymorphicModel
from polymorphic.query import PolymorphicQuerySet

from peachjam.analysis.html import generate_toc_json_from_html, wrap_toc_entries_in_divs
from peachjam.decorators import DocumentDecorator
from peachjam.frbr_uri import (
    FRBR_URI_DOCTYPE_CHOICES,
    FRBR_URI_DOCTYPES,
    validate_frbr_uri_component,
    validate_frbr_uri_date,
)
from peachjam.helpers import pdfjs_to_text
from peachjam.models.attachments import Image
from peachjam.models.citations import CitationLink, ExtractedCitation
from peachjam.models.enrichments import ProvisionCitation, ProvisionCitationCount
from peachjam.models.lifecycle import AttributeHooksMixin
from peachjam.models.settings import pj_settings
from peachjam.pipelines import DOC_MIMETYPES, word_pipeline
from peachjam.xmlutils import parse_html_str

log = logging.getLogger(__name__)


@dataclass
class BreadCrumb:
    """A simple dataclass to represent a breadcrumb."""

    name: str
    url: str


class Label(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, unique=True, null=False, blank=False
    )
    code = models.SlugField(_("code"), max_length=1024, unique=True)
    level = models.CharField(
        _("level"),
        max_length=1024,
        null=False,
        blank=False,
        default="info",
        help_text="One of: primary, secondary, success, danger, warning or info.",
    )

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("label")
        verbose_name_plural = _("labels")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"


class DocumentNature(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    code = models.SlugField(_("code"), max_length=1024, null=False, unique=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("document nature")
        verbose_name_plural = _("document natures")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Locality(models.Model):
    name = models.CharField(_("name"), max_length=255, null=False)
    jurisdiction = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name=_("jurisdiction")
    )
    code = models.CharField(_("code"), max_length=20, null=False)
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        verbose_name = _("locality")
        verbose_name_plural = _("localities")
        ordering = ["name"]
        unique_together = ["name", "jurisdiction"]

    def place_code(self):
        return f"{self.jurisdiction.pk.lower()}-{self.code}"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("place", kwargs={"code": self.place_code()})


class Work(models.Model):
    frbr_uri = models.CharField(
        _("FRBR URI"), max_length=1024, null=False, blank=False, unique=True
    )
    # components of the FRBR URI, useful for dashboards; derived from the frbr_uri field when saved
    frbr_uri_country = models.CharField(
        _("FRBR URI country"),
        max_length=2,
        null=False,
        blank=False,
    )
    frbr_uri_locality = models.CharField(
        _("FRBR URI locality"),
        max_length=100,
        null=True,
        blank=True,
    )
    frbr_uri_place = models.CharField(
        _("FRBR URI place"),
        max_length=100,
        null=False,
        blank=False,
    )
    frbr_uri_doctype = models.CharField(
        _("FRBR URI doctype"),
        max_length=20,
        null=False,
        blank=False,
    )
    frbr_uri_subtype = models.CharField(
        _("FRBR URI subtype"),
        max_length=100,
        null=True,
        blank=True,
    )
    frbr_uri_actor = models.CharField(
        _("FRBR URI actor"),
        max_length=100,
        null=True,
        blank=True,
    )
    frbr_uri_date = models.CharField(
        _("FRBR URI date"),
        max_length=10,
        null=False,
        blank=False,
    )
    frbr_uri_number = models.CharField(
        _("FRBR URI number"),
        max_length=1024,
        null=False,
        blank=False,
    )
    title = models.CharField(_("title"), max_length=4096, null=False, blank=False)
    languages = ArrayField(
        models.CharField(max_length=3),
        null=False,
        blank=False,
        default=list,
        verbose_name=_("languages"),
    )
    partner = models.ForeignKey(
        "peachjam.Partner",
        null=True,
        blank=True,
        verbose_name=_("partner"),
        help_text=_("Publication partner"),
        on_delete=models.SET_NULL,
    )

    # work score details

    # the rank (weight) of this work in the graph network, computer by peachjam.analysis.ranker
    pagerank = models.FloatField(_("pagerank"), null=True, blank=False, default=0.0)
    # normalised pagerank using min/max normalisation
    pagerank_normalized = models.FloatField(_("pagerank normalized"), default=0.0)
    # number of outgoing citations
    n_cited_works = models.IntegerField(_("number of cited works"), default=0)
    # number of incoming citations
    n_citing_works = models.IntegerField(_("number of incoming citations"), default=0)
    # normalised number of incoming citations: min/max normalisation of log(n_citing_works + 1)
    n_citing_works_normalized = models.FloatField(
        _("number of incoming citations normalized"), default=0.0
    )
    # weighted combination of pagerank_normalized and n_citing_works_normalized
    authority_score = models.FloatField(_("authority score"), default=0.0)

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
        # delete existing extracted citations
        ExtractedCitation.objects.filter(citing_work=self).delete()
        cited_works = self.fetch_cited_works_frbr_uris()
        works = {
            w.frbr_uri: w for w in Work.objects.filter(frbr_uri__in=cited_works.keys())
        }

        for frbr_uri, treatments in cited_works.items():
            work = works.get(frbr_uri)
            if work:
                extracted_citations, _ = ExtractedCitation.objects.get_or_create(
                    citing_work=self, target_work=work
                )
                extracted_citations.treatments.set(treatments)

    def fetch_cited_works_frbr_uris(self):
        """Retrieves a mapping of cited work FRBR URIs and treatments,
        taken from CitationLink objects(for PDFs) and all <a href="/akn/..."> embedded HTML links.
        Returns:
            dict: {work_frbr_uri: [treatments]}
        """
        work_frbr_uris = defaultdict(list)

        for doc in self.documents.all():
            for frbr_uri, treatments in doc.get_cited_work_frbr_uris().items():
                work_frbr_uris[frbr_uri].extend(treatments)

        # remove duplicate treatments and self citations
        work_frbr_uris = {
            frbr_uri: list(set(treatments))
            for frbr_uri, treatments in work_frbr_uris.items()
            if frbr_uri != self.frbr_uri
        }

        return work_frbr_uris

    def cited_works(self):
        """Returns a list of works cited by the current work."""
        return ExtractedCitation.for_citing_works(self).values("target_work")

    def works_citing_current_work(self):
        """Returns a list of works that cite the current work."""
        return ExtractedCitation.for_target_works(self).values("citing_work")

    def save(self, *args, **kwargs):
        self.explode_frbr_uri()
        super().save(*args, **kwargs)

    def explode_frbr_uri(self):
        frbr_uri = FrbrUri.parse(self.frbr_uri)
        self.frbr_uri_country = frbr_uri.country
        self.frbr_uri_locality = frbr_uri.locality
        self.frbr_uri_place = frbr_uri.place
        self.frbr_uri_doctype = frbr_uri.doctype
        self.frbr_uri_subtype = frbr_uri.subtype
        self.frbr_uri_actor = frbr_uri.actor
        self.frbr_uri_date = frbr_uri.date
        self.frbr_uri_number = frbr_uri.number

    def get_absolute_url(self):
        return reverse("document_detail", kwargs={"frbr_uri": self.frbr_uri[1:]})

    def __str__(self):
        return f"{self.frbr_uri} - {self.title}"


class CoreDocumentManager(PolymorphicManager):
    def get_queryset(self):
        # defer expensive fields
        return super().get_queryset().defer("content_html", "toc_json", "metadata_json")

    def get_qs_no_defer(self):
        return super().get_queryset()


class CoreDocumentQuerySet(PolymorphicQuerySet):
    def latest_expression(self):
        """Select only the most recent expression for documents from the same work."""
        return self.distinct("work_id").order_by("work_id", "-date")

    def preferred_language(self, language):
        """Return documents whose language match the preferred one,
        or return all docs if there are no documents in the preferred language.
        """
        return self.filter(
            models.Q(language_id__iso_639_3=language)
            | ~models.Q(work__languages__contains=[language])
        )

    def best_for_frbr_uri(self, frbr_uri, lang):
        """Get the best object for this FRBR URI, which could be an expression or a work URI.
        Returns an (object, exact) tuple, where exact is a boolean indicating if the match was an exact one,
        or a guess."""
        if "@" in frbr_uri:
            obj = self.filter(expression_frbr_uri=frbr_uri).first()
            return obj, True

        # try looking based on the work URI instead, and use the latest expression
        qs = CoreDocument.objects.filter(work__frbr_uri=frbr_uri)

        # first, look for one in the user's preferred language
        if lang:
            obj = qs.filter(language__pk=lang).latest_expression().first()
            if obj:
                return obj, False

        # try the default site language
        lang = pj_settings().default_document_language
        if lang:
            obj = qs.filter(language=lang).latest_expression().first()
            if obj:
                return obj, False

        # just get any one
        obj = qs.latest_expression().first()
        return obj, False

    def for_document_table(self):
        """Apply the appropriate prefetches for data to show in the document table view."""
        return self.select_related(
            "nature", "work", "jurisdiction", "locality"
        ).prefetch_related("labels", "taxonomies", "taxonomies__topic")


class CoreDocument(AttributeHooksMixin, PolymorphicModel):
    # There are three ways of indicating a document's type:
    #
    # 1. doc_type: This is historical and not widely used, since PolymorphicModel does the bulk of the work for us.
    #              It is used where we need to know the django Model to use for the document. There is a chance
    #              we could remove this and rely on PolymorphicModel.
    #
    # 2. frbr_uri_doctype: the doc type used in the FRBR URI. There is a list of allowed values. Usually, each
    #                      value has a concrete django Model, such as act -> Legislation.
    #
    # 3. nature: a human-friendly label for the document type, which can be more specific than the other two.

    DOC_TYPE_CHOICES = (
        ("core_document", "Core Document"),
        ("bill", "Bill"),
        ("gazette", "Gazette"),
        ("generic_document", "Generic Document"),
        ("judgment", "Judgment"),
        ("legal_instrument", "Legal Instrument"),
        ("legislation", "Legislation"),
        ("book", "Book"),
        ("journal_article", "JournalArticle"),
        ("causelist", "Cause List"),
    )

    # The name of the default nature to use for this type of document, if one is not set. This allows us to ensure
    # that all documents have a nature.
    default_nature = ("document", "Document")

    # the decorator is a plugin-point to make changes to a document pre- and post-save
    decorator = DocumentDecorator()

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
    title = models.CharField(_("title"), max_length=4096, null=False, blank=False)
    date = models.DateField(_("date"), null=False, blank=False, db_index=True)
    source_url = models.URLField(
        _("source URL"), max_length=2048, null=True, blank=True
    )
    citation = models.CharField(_("citation"), max_length=4096, null=True, blank=True)
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
        null=False,
        blank=False,
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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("created by"),
    )
    allow_robots = models.BooleanField(
        _("allow robots"),
        default=True,
        db_index=True,
        help_text=_("Allow this document to be indexed by search engine robots."),
    )

    published = models.BooleanField(
        _("published"),
        default=True,
        db_index=True,
        help_text=_("Is this document published and visible on the website?"),
    )
    metadata_json = models.JSONField(_("metadata JSON"), null=True, blank=True)

    # options for the FRBR URI doctypes
    frbr_uri_doctypes = FRBR_URI_DOCTYPES
    labels = models.ManyToManyField(Label, verbose_name=_("labels"), blank=True)

    # ingestor responsible for managing this document
    ingestor = models.ForeignKey(
        "peachjam.Ingestor", on_delete=models.SET_NULL, null=True, blank=True
    )

    restricted = models.BooleanField(
        default=False,
        help_text=_("Restrict access to this document to selected groups."),
    )

    # for caching parsed html
    _content_html_tree = None

    class Meta:
        ordering = ["doc_type", "title"]
        permissions = [
            ("can_delete_own_document", "Can delete own document"),
            ("can_edit_own_document", "Can edit own document"),
            ("can_edit_advanced_fields", "Can edit advanced fields"),
            ("can_debug_document", "Can do document debugging"),
            ("can_view_document_summary", "Can view document summary"),
            ("can_generate_judgment_summary", "Can generate judgment summary"),
            ("can_offline", "Can save content for offline use"),
            ("can_view_historical_legislation", "Can view historical legislation"),
            ("can_view_case_history", "Can view case history"),
            ("can_view_provision_changes", "Can view provision changes"),
        ]

    def __str__(self):
        return f"{self.doc_type} - {self.title}"

    def get_all_fields(self):
        return self._meta.get_fields()

    def get_absolute_url(self):
        return reverse(
            "document_detail", kwargs={"frbr_uri": self.expression_frbr_uri[1:]}
        )

    @property
    def year(self):
        return self.date.year

    def full_clean(self, *args, **kwargs):
        # give ourselves and subclasses a chance to pre-populate derived fields before cleaning
        self.pre_save()
        super().full_clean(*args, **kwargs)

    def set_content_html(self, content_html):
        """Update the content HTML for this document. This cleans the HTML and generates a TOC if necessary. This is
        the preferred way of setting the content_html field."""
        if not self.content_html_is_akn:
            self.content_html = self.clean_content_html(content_html)
            self.update_toc_json_from_html()
            self._content_html_tree = None

    @property
    def content_html_tree(self) -> html.HtmlElement:
        """A parsed version of the content HTML. This is cached for performance."""
        if self._content_html_tree is None:
            self._content_html_tree = parse_html_str(self.content_html)
        return self._content_html_tree

    def update_toc_json_from_html(self):
        if self.content_html:
            root = self.content_html_tree
            self.toc_json = generate_toc_json_from_html(root)
            wrap_toc_entries_in_divs(root, self.toc_json)
            self.content_html = html.tostring(root, encoding="unicode")
        else:
            self.toc_json = []

    def clean_html_field(self, html):
        if not html:
            return None

        # return None if the HTML doesn't have any content
        try:
            root = parse_html_str(html)
            iframes = root.xpath("//iframe")
            if iframes:
                return html

            text = "".join(root.itertext()).strip()
            text = re.sub(r"\s", "", text)
            if not text:
                return None
        except (ValueError, ParserError):
            return None

        return html

    def clean_content_html(self, content_html):
        """Ensure that content_html is not just whitespace HTML. Returns the cleaned value."""
        return self.clean_html_field(content_html)

    def clean(self):
        super().clean()
        try:
            FrbrUri.parse(self.work_frbr_uri)
        except ValueError:
            raise ValidationError(
                {
                    "work_frbr_uri": _("Invalid FRBR URI: %(uri)s")
                    % {"uri": self.work_frbr_uri}
                }
            )

        if (
            self.__class__.objects.filter(expression_frbr_uri=self.expression_frbr_uri)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                _("Document with this Expression FRBR URI already exists!")
                + " "
                + self.expression_frbr_uri
            )

    def generate_expression_frbr_uri(self):
        try:
            frbr_uri = FrbrUri.parse(self.work_frbr_uri)
            frbr_uri.expression_date = f"@{datestring(self.date)}"
            frbr_uri.language = self.language.iso_639_3
        except ValueError as e:
            raise ValidationError(f"Invalid FRBR URI: {self.work_frbr_uri}") from e

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

    def set_frbr_uri_subtype(self):
        # default the subtype to the nature code, unless the nature is the default nature
        if self.nature and self.nature.code != self.default_nature[0]:
            self.frbr_uri_subtype = self.nature.code

    def set_frbr_uri_number(self):
        # default the number to a slugified title
        if not self.frbr_uri_number and self.title:
            self.frbr_uri_number = slugify(self.title)

    def set_nature(self):
        # provide a default nature if it's not already set
        # use hasattr() because otherwise we'd get a DoesNotExist exception
        if not hasattr(self, "nature"):
            code, name = self.default_nature
            self.nature = DocumentNature.objects.get_or_create(
                code=code, defaults={"name": name}
            )[0]

    def prepare_and_set_expression_frbr_uri(self):
        self.set_nature()
        self.set_frbr_uri_subtype()
        self.set_frbr_uri_number()
        self.assign_frbr_uri()
        self.expression_frbr_uri = self.generate_expression_frbr_uri()

    def pre_save(self):
        """Pre-populate various fields before saving or running full_clean."""
        self.prepare_and_set_expression_frbr_uri()

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

        if self.decorator:
            self.decorator.pre_save(self)

    def post_save(self):
        if self.decorator:
            self.decorator.post_save(self)

    def save(self, *args, **kwargs):
        # give ourselves and subclasses a chance to pre-populate derived fields before saving,
        # in case full_clean() has not yet been called
        self.pre_save()
        super().save(*args, **kwargs)
        self.post_save()

    def extract_citations(self):
        """Run citation extraction on this document. If the document has content_html,
        extraction will be run on that. Otherwise, if the document as a PDF source file,
        extraction will be run on that.
        """
        from peachjam.analysis.citations import citation_analyser

        self.delete_citations()
        return citation_analyser.extract_citations(self)

    def extract_provision_citations(self):
        """Extract citation contexts for this document. This will extract contexts for all citations
        in the document, and update the ExtractedCitationContext objects.
        """
        from peachjam.analysis.citations import citation_analyser

        removed_work_ids = self.delete_provision_citations()
        citation_analyser.update_provision_citations(self)
        current_work_ids = set(
            ProvisionCitation.objects.filter(citing_document=self)
            .values_list("work_id", flat=True)
            .distinct()
        )
        affected_work_ids = removed_work_ids | current_work_ids
        if affected_work_ids:
            ProvisionCitationCount.refresh_for_works(affected_work_ids)

    def delete_provision_citations(self):
        """Delete existing provision citations for this document."""
        qs = ProvisionCitation.objects.filter(citing_document=self)
        work_ids = set(qs.values_list("work_id", flat=True).distinct())
        qs.delete()
        return work_ids

    def delete_citations(self):
        """Delete existing citation links and added citations from this document."""
        from peachjam.models.citations import CitationLink

        CitationLink.objects.filter(document=self).delete()

        if self.content_html and not self.content_html_is_akn:
            # delete existing citations in html
            root = self.content_html_tree
            deleted = False
            for a in root.xpath('//a[starts-with(@href, "/akn/")]'):
                unwrap_element(a)
                deleted = True
            if deleted:
                self.content_html = html.tostring(root, encoding="unicode")

    def extract_content_from_source_file(self):
        """Re-extract content from DOCX source files, overwriting anything in content_html and associated images.

        This requires that the document has already been saved, in order to associate image attachments.
        """
        result = False
        if (
            not self.content_html_is_akn
            and hasattr(self, "source_file")
            and self.source_file.mimetype in DOC_MIMETYPES
        ):
            context = PipelineContext(word_pipeline)
            context.source_file = self.source_file.file
            word_pipeline(context)
            self.set_content_html(context.html_text)

            for img in self.images.all():
                img.delete()

            for attachment in context.attachments:
                if attachment.content_type.startswith("image/"):
                    img = Image.from_docpipe_attachment(attachment)
                    img.document = self
                    img.save()
                    self.images.add(img)

            result = True

        # always update document text
        self.update_text_content()

        return result

    def prepare_content_html_for_pdf(self):
        """Prepare the content HTML for PDF generation by inlining images as base64."""
        if not self.content_html:
            return None

        # Parse the HTML content
        root = parse_html_str(self.content_html)
        images = {i.filename: i for i in self.images.all()}

        # inline images
        for img_tag in root.xpath("//img[@src]"):
            src = img_tag.attrib["src"]
            if src.startswith("media/"):
                # strip media prefix
                src = src[6:]

            # Look up the image file associated with the document
            image = images.get(src)
            if image:
                try:
                    # Read the image file and encode it as base64
                    base64_data = base64.b64encode(image.file.read()).decode("utf-8")
                    img_tag.attrib[
                        "src"
                    ] = f"data:{image.mimetype};base64,{base64_data}"
                except Exception as e:
                    log.warning(f"Failed to inline image {src}: {e}", exc_info=e)

        # inline CSS for the inject pj-anonymisation-notice
        # TODO: this is a bit of a hack; if we inline other css, find a better way
        notice = root.get_element_by_id("pj-anonymisation-notice", None)
        if notice is not None:
            notice.set("style", "text-align: center; color: red; margin-bottom: 1em;")

        # Return the modified HTML as a string
        return etree.tostring(root, encoding="utf-8", method="html")

    def convert_html_to_pdf(self):
        """Generate a PDF from the HTML content of this file. Returns an open file handle to the PDF data."""
        with tempfile.NamedTemporaryFile(suffix=".html") as html_file:
            html_file.write(self.prepare_content_html_for_pdf())
            html_file.flush()
            html_file.seek(0)
            pdf, _ = soffice_convert(html_file, "html", "pdf")
            return pdf

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

    def get_provision_by_eid(self, eid):
        if not self.content_html or not self.content_html_is_akn:
            return None

        # Find element with data-eId
        xpath = f"//*[@data-eid='{eid}']"
        elements = self.content_html_tree.xpath(xpath)

        if elements:
            return etree.tostring(elements[0], encoding="unicode", method="html")
        return None

    def get_content_as_text(self):
        """Get the document content as plain text."""
        if not hasattr(self, "document_content"):
            self.update_text_content()
        return self.document_content.content_text

    def update_text_content(self):
        """Update the extracted text content."""
        self.document_content = DocumentContent.update_or_create_for_document(self)

    def get_cited_work_frbr_uris(self):
        """Get a list of parsed FRBR URIs of works cited by this document."""
        work_frbr_uris = {}

        if self.content_html:
            root = html.fromstring(self.content_html)
            if self.content_html_is_akn:
                # get AKN links in the document content, except those in remarks or in the generated
                # coverpage (which is outside the akn-akomaNtoso root)
                xpath = (
                    '//*[contains(@class, "akn-akomaNtoso")]//a[starts-with(@data-href, "/akn") and '
                    'not(ancestor::*[contains(@class, "akn-remark")])]'
                )
                attr = "data-href"
            else:
                xpath = '//a[starts-with(@href, "/akn")]'
                attr = "href"

            for a in root.xpath(xpath):
                try:
                    work_frbr_uri = FrbrUri.parse(a.attrib[attr]).work_uri()
                    # here we can add a list of citation treatments as values
                    work_frbr_uris[work_frbr_uri] = []
                except ValueError:
                    # ignore malformed FRBR URIs
                    pass
        else:
            for citation_link in CitationLink.objects.filter(document_id=self.pk):
                try:
                    uri = FrbrUri.parse(citation_link.url)
                    uri.portion = None
                    work_frbr_uri = uri.work_uri()
                    work_frbr_uris[work_frbr_uri] = []
                except ValueError:
                    # ignore malformed FRBR URIs
                    pass

        return work_frbr_uris

    def search_penalty(self):
        """Optionally provide a penalty for this document in search results. This cannot be zero or None."""
        # provide a very small number instead of zero
        return 0.0000001

    def get_doc_type_display(self):
        """Human-friendly type of this document, which is always the nature, since that cannot be null."""
        return self.nature.name

    def ingestor_edit_url(self):
        if self.ingestor:
            return self.ingestor.get_edit_url(self)

    @cached_property
    def listing_taxonomies(self):
        """Get a list of DocumentTopic objects to display in the document listing view. Assumes that the taxonomies
        have been pre-fetched."""
        return [t for t in self.taxonomies.all() if t.topic.show_in_document_listing]

    def friendly_provision_title(self, provision_eid):
        """Generate a friendly title for the provision with the given eid. This assumes the document is AKN HTML
        and has a TOC JSON.
        """
        if self.toc_json:

            def find_toc_item(toc, eid):
                for item in toc:
                    if item["id"] == eid:
                        return item

                    if item["id"] and eid.startswith(f"{item['id']}__"):
                        if item["children"]:
                            # descend into children
                            found = find_toc_item(item["children"], eid)
                            if found:
                                return found

                        # closest match
                        return item

            # walk down the TOC and try to find the item, or the closest entry to it
            item = find_toc_item(self.toc_json, provision_eid)
            if item:
                if item["id"] == provision_eid:
                    return item["title"]

                # we didn't find it, so join up the gap between the item we did find and the real provision
                if self.content_html and self.content_html_is_akn:
                    root = self.content_html_tree
                    element = root.get_element_by_id(provision_eid, None)
                    nums = []

                    # walk upwards from our actual element up to item, gathering akn-nums along the way
                    while element is not None:
                        for kid in element:
                            if "akn-num" in (kid.get("class") or ""):
                                if kid.text:
                                    nums.append(kid.text)
                                break

                        # have we topped out, either at the item or above it (and their ids no longer match)
                        if element.get("id") and (
                            element.get("id") == item["id"]
                            or not element.get("id").startswith(item["id"])
                        ):
                            break

                        element = element.getparent()

                    nums.append(item["title"])
                    nums.reverse()
                    return " ".join(nums)

        # fallback to the eid
        return provision_eid

    def get_breadcrumbs(self):
        """Get a list of breadcrumbs for this document, suitable for rendering in a template."""
        crumbs = []
        if self.decorator:
            crumbs = self.decorator.get_breadcrumbs(self)
        return crumbs


class AlternativeName(models.Model):
    document = models.ForeignKey(
        CoreDocument,
        on_delete=models.CASCADE,
        related_name="alternative_names",
        verbose_name=_("document"),
    )
    title = models.CharField(
        _("Law report citation/Alternative known name"),
        max_length=1024,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = _("alternative name")
        verbose_name_plural = _("alternative names")

    def __str__(self):
        return self.title


class DocumentContent(models.Model):
    """Support model for storing the actual content of the document. This means it is never loaded in listing views
    which makes queries faster.
    """

    document = models.OneToOneField(
        CoreDocument,
        on_delete=models.CASCADE,
        related_name="document_content",
        verbose_name=_("document"),
    )
    # the raw text of the document, extracted either from the source file or the HTML
    # this makes re-indexing for faster, because we don't need to re-extract the text from the source document
    content_text = models.TextField(
        blank=True, null=True, verbose_name=_("document text")
    )
    # option XML content of the document
    content_xml = models.TextField(
        blank=True, null=True, verbose_name=_("document XML")
    )

    class Meta:
        verbose_name = _("document content")
        verbose_name_plural = _("document contents")

    def akn_doc(self):
        """Get a cobalt StructureDocument instance for this document's XML, assuming it is AKN XML."""
        if self.content_xml:
            return StructuredDocument.for_document_type(self.document.frbr_uri_doctype)(
                self.content_xml
            )

    @classmethod
    def update_or_create_for_document(cls, document):
        """Extract the content from a document, whatever its format is."""
        text = ""
        if document.content_html:
            # it's html, grab the text from the html tree
            root = document.content_html_tree
            text = " ".join(root.itertext())

        elif hasattr(document, "source_file"):
            if document.source_file.pk:
                # get the text from the source file, via PDF if necessary
                with tempfile.NamedTemporaryFile() as tmp:
                    # convert document to pdf and then extract the text
                    pdf = document.source_file.as_pdf()
                    if pdf:
                        shutil.copyfileobj(pdf, tmp)
                        pdf.seek(0)
                        tmp.flush()
                        text = pdfjs_to_text(tmp.name)
                        # some PDFs have nulls, which breaks SQL insertion
                        # replace rather than deleting to keep string length the same
                        text = text.replace("\0", " ")

        doc_content = DocumentContent.objects.update_or_create(
            document=document, defaults={"content_text": text}
        )[0]
        document.document_content = doc_content
        return doc_content


def get_country_and_locality(code):
    if not code:
        return None, None

    if "-" in code:
        cty_code, locality_code = code.split("-", 1)
        country = Country.objects.get(pk=cty_code.upper())
        locality = Locality.objects.get(jurisdiction=country, code=locality_code)
    else:
        country = Country.objects.get(pk=code.upper())
        locality = None
    return country, locality


def get_country_and_locality_or_404(code):
    try:
        return get_country_and_locality(code)
    except ObjectDoesNotExist:
        raise Http404()
