from django.db import models

from peachjam.models import CoreDocument


class Book(CoreDocument):
    publisher = models.CharField(max_length=2048)

    def save(self, *args, **kwargs):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "book"
        self.doc_type = "book"
        return super().save(*args, **kwargs)


class Journal(CoreDocument):
    publisher = models.CharField(max_length=2048)

    def save(self, *args, **kwargs):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "journal"
        self.doc_type = "journal"
        return super().save(*args, **kwargs)
