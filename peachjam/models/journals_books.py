from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from martor.models import MartorField
from martor.utils import markdownify

from peachjam.decorators import BookDecorator, JournalArticleDecorator
from peachjam.models import CoreDocument


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
    title = models.CharField(max_length=512)
    slug = models.SlugField(max_length=512, unique=False, blank=True, null=True)
    doi = models.CharField(max_length=255, verbose_name="Directory of Indexing (DOI)")

    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class JournalArticle(CoreDocument):

    decorator = JournalArticleDecorator()

    publisher = models.CharField(max_length=2048)
    default_nature = ("journal_article", "Journal article")
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

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "journal-article"
        self.doc_type = "journal_article"
        return super().pre_save()


class VolumeIssue(models.Model):

    title = models.CharField(
        max_length=255,
        help_text="The volume and issue number (e.g., 'Vol 58, Issue 1' or 'Volume 58')",
    )
    slug = models.SlugField(max_length=255, unique=False, blank=True, null=True)
    issue = models.IntegerField()
    journal = models.ForeignKey(
        "peachjam.Journal",  # String reference avoids circular import issues
        on_delete=models.CASCADE,
        related_name="volumes",
    )
    year = models.IntegerField(
        help_text="Publication year used for sorting and faceting",
        db_index=True,  # Indexing added since this is key for sorting/faceting
    )

    class Meta:
        ordering = ["-year", "title"]
        verbose_name = "Volume/Issue"
        verbose_name_plural = "Volumes/Issues"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.year})"
