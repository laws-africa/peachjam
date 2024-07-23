from django.db import models
from martor.models import MartorField
from martor.utils import markdownify

from peachjam.models import CoreDocument, DocumentNature


class Book(CoreDocument):
    publisher = models.CharField(max_length=2048)
    content_markdown = MartorField(blank=True, null=True)

    def delete_citations(self):
        super().delete_citations()
        # reset the HTML back to the original from markdown, because delete_citations()
        # removes any embedded akn links
        if self.content_markdown:
            self.convert_content_markdown()

    def convert_content_markdown(self):
        self.content_html = markdownify(self.content_markdown or "")

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        if not self.nature:
            self.nature = DocumentNature.objects.get_or_create(
                code="book", defaults={"name": "Book"}
            )[0]
        self.doc_type = "book"
        return super().pre_save()


class Journal(CoreDocument):
    publisher = models.CharField(max_length=2048)

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        if not self.nature:
            self.nature = DocumentNature.objects.get_or_create(
                code="journal", defaults={"name": "Journal"}
            )[0]
        self.doc_type = "journal"
        return super().pre_save()
