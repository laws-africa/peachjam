from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.translation import gettext_lazy as _
from markdown.extensions.toc import slugify
from martor.models import MartorField
from martor.utils import markdownify

from peachjam.decorators import BookDecorator, JournalArticleDecorator
from peachjam.models import Author, CoreDocument


class Book(CoreDocument):

    decorator = BookDecorator()

    publisher = models.CharField(max_length=2048)
    content_markdown = MartorField(blank=True, null=True)
    default_nature = ("book", "Book")

    def delete_citations(self):
        super().delete_citations()
        # reset the HTML back to the original from markdown, because delete_citations()
        # removes any embedded akn links
        if self.content_markdown:
            self.convert_content_markdown()

    def convert_content_markdown(self):
        self.set_content_html(markdownify(self.content_markdown or ""))

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "book"
        self.doc_type = "book"
        return super().pre_save()


class Journal(models.Model):
    title = models.CharField(max_length=512, unique=True, blank=False, null=False)
    slug = models.SlugField(max_length=512, unique=True)
    doi = models.CharField(
        max_length=255, verbose_name="Digital Object Identifier (DOI)"
    )

    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


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
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "journal-article"
        self.doc_type = "journal_article"
        return super().pre_save()

    def author_list(self):
        return list(self.authors.all())


class VolumeIssue(models.Model):

    title = models.CharField(
        max_length=2048,
        help_text="The volume and issue number (e.g., 'Vol 58, Issue 1' or 'Volume 58')",
    )
    journal = models.ForeignKey(
        "peachjam.Journal",
        on_delete=models.CASCADE,
        related_name="volumes",
    )
    slug = models.SlugField(max_length=255, unique=True, blank=False)

    class Meta:
        ordering = ["title"]
        verbose_name = "Volume/Issue"
        verbose_name_plural = "Volumes/Issues"
        unique_together = [["journal", "title"]]

    def save(self, *args, **kwargs):
        self.slug = slugify(f"{self.journal.title} {self.title}", "-")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
