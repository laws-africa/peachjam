from django.db import models
from django.urls import reverse
from .core_document_model import CoreDocument


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


class GenericDocument(models.Model):
    document = models.OneToOneField(CoreDocument, on_delete=models.PROTECT, null=False, blank=False)
    authoring_body = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=False, blank=False)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=False, blank=False)

    class Meta:
        ordering = ['document__title']

    def __str__(self):
        return self.document.title

    def get_absolute_url(self):
        return reverse('generic_document_detail', args=str(self.id))


class LegalInstrument(models.Model):
    document = models.OneToOneField(CoreDocument, on_delete=models.PROTECT, null=False, blank=False)
    authoring_body = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=False, blank=False)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=False, blank=False)

    class Meta:
        ordering = ['document__title']

    def __str__(self):
        return self.document.title

    def get_absolute_url(self):
        return reverse('legal_instrument_detail', args=str(self.id))


class Legislation(models.Model):
    document = models.OneToOneField(CoreDocument, on_delete=models.PROTECT, null=False, blank=False)
    toc_json = models.JSONField(null=True, blank=True)
    metadata_json = models.JSONField(null=False, blank=False)

    class Meta:
        ordering = ['document__title']
        verbose_name_plural = 'Legislation'

    def __str__(self):
        return self.document.title

    def get_absolute_url(self):
        return reverse('legislation_detail', args=str(self.id))
