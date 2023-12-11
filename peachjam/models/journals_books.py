from django.db import models
from martor.models import MartorField

from peachjam.models import CoreDocument, DocumentNature


class Book(CoreDocument):
    publisher = models.CharField(max_length=2048)
    content_markdown = MartorField(blank=True, null=True)

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
