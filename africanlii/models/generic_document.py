from django.db import models
from django.urls import reverse
from .core_document_model import CoreDocumentModel

class DocumentNature(models.Model):
  name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
  description = models.TextField(blank=True)

  def __str__(self):
    return self.name

class AuthoringBody(models.Model):
  name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
  description = models.TextField(blank=True)

  def __str__(self):
    return self.name

  class Meta:
    ordering = ['name']

class BaseGenericDocument(CoreDocumentModel):
    authoring_body = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=False, blank=False)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=False, blank=False)
    
    def __str__(self):
        return self.title
    class Meta:
        abstract = True

class GenericDocument(BaseGenericDocument):
    def get_absolute_url(self):
        return reverse('generic_document_detail', args=str(self.id))

class LegalInstrument(BaseGenericDocument):
    def get_absolute_url(self):
        return reverse('legal_instrument_detail', args=str(self.id))

class Legislation(CoreDocumentModel):
    toc_json = models.JSONField(null=True, blank=True) 
    metadata_json = models.JSONField(null=False, blank=False)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('legislation_detail', args=str(self.id))
