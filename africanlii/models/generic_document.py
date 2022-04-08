from django.db import models
from django.urls import reverse
from peachjam.models import CoreDocument


class AuthoringBody(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Authoring bodies'


class DocumentNature(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class GenericDocument(CoreDocument):
    authoring_body = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=False, blank=False)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=False, blank=False)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = 'generic_document'
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('generic_document_detail', args=str(self.id))


class LegalInstrument(CoreDocument):
    authoring_body = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=False, blank=False)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=False, blank=False)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = 'legal_instrument'
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('legal_instrument_detail', args=str(self.id))


class Legislation(CoreDocument):
    toc_json = models.JSONField(null=True, blank=True)
    metadata_json = models.JSONField(null=False, blank=False)

    class Meta:
        verbose_name_plural = 'Legislation'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = 'legislation'
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('legislation_detail', args=str(self.id))
