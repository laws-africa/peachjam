import re

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_lifecycle import BEFORE_SAVE
from markdown.extensions.toc import slugify
from martor.models import MartorField
from martor.utils import markdownify

from peachjam.decorators import BookDecorator, JournalArticleDecorator
from peachjam.models import Author, CoreDocument
from peachjam.models.lifecycle import on_attribute_changed


class Book(CoreDocument):

    decorator = BookDecorator()

    publisher = models.CharField(max_length=2048)
    content_markdown = MartorField(blank=True, null=True)
    default_nature = ("book", "Book")

    @on_attribute_changed(
        BEFORE_SAVE,
        ["content_markdown"],
        ["DocumentContent.source_html"],
    )
    def convert_content_markdown(self):
        doc_content = self.get_or_create_document_content()
        doc_content.set_source_html(markdownify(self.content_markdown or ""))

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "book"
        self.doc_type = "book"
        return super().pre_save()


class Journal(models.Model):
    title = models.CharField(max_length=512, unique=True, blank=False, null=False)
    slug = models.SlugField(max_length=512, unique=True)
    doi = models.CharField(
        max_length=255,
        verbose_name="Digital Object Identifier (DOI)",
        blank=True,
        null=True,
    )

    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("journal_detail", args=[self.slug])


class JournalArticle(CoreDocument):

    decorator = JournalArticleDecorator()

    publisher = models.CharField(max_length=2048)
    default_nature = ("journal_article", "Journal article")
    author_label = Author.model_label
    author_label_plural = Author.model_label_plural
    journal = models.ForeignKey(
        "peachjam.Journal",
        on_delete=models.PROTECT,
        related_name="articles",
        null=True,  # MUST be null initially because existing rows have no journal
        blank=True,
    )
    volume = models.ForeignKey(
        "peachjam.VolumeIssue",
        on_delete=models.PROTECT,
        related_name="articles",
        null=True,
        blank=True,
    )
    authors = models.ManyToManyField(
        "peachjam.Author",
        blank=True,
        related_name="articles",
    )
    page_range = models.CharField(
        _("page range"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Page range, e.g. pages 17-24"),
    )

    def pre_save(self):
        if (
            self.volume
            and self.journal_id
            and self.journal_id != self.volume.journal_id
        ):
            self.volume = None
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "journal-article"
        self.doc_type = "journal_article"
        return super().pre_save()

    def author_list(self):
        return list(self.authors.all())


VOLUME_ISSUE_TITLE_RE = re.compile(
    r"Vol[.\s]*(\d+)[,\s]*No[.\s]*(\d+).*?(\d{4})", re.IGNORECASE
)

MONTH_NAMES = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


class VolumeIssue(models.Model):

    title = models.CharField(
        max_length=2048,
        help_text="The volume and issue number, e.g. 'Vol. 3 No.1 1993' or 'Vol. 3 No.1 - 1993'.",
    )
    journal = models.ForeignKey(
        "peachjam.Journal",
        on_delete=models.CASCADE,
        related_name="volumes",
    )
    slug = models.SlugField(max_length=255, unique=False, blank=False)

    class Meta:
        ordering = ["title"]
        verbose_name = "Volume/Issue"
        verbose_name_plural = "Volumes/Issues"
        unique_together = [["journal", "title"], ["journal", "slug"]]

    def clean(self):
        if self.title:
            if not VOLUME_ISSUE_TITLE_RE.search(self.title):
                raise ValidationError(
                    {
                        "title": _(
                            "Title must include a volume number, issue number, month, and year, "
                            "e.g. 'Vol. 3 No.1 - January 1993'."
                        )
                    }
                )
            if not any(w.lower() in MONTH_NAMES for w in self.title.split()):
                raise ValidationError(
                    {
                        "title": _(
                            "Title must include a month name, "
                            "e.g. 'Vol. 3 No.1 - January 1993'."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title, "-")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
