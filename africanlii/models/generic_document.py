from django.db import models
from django.urls import reverse
from .core_document_model import CoreDocumentModel

class GenericDocument(CoreDocumentModel):
    """ 
    This model represents generic documents.
    """
    nature = models.CharField(max_length=1024, null=True, blank=True)
    author = models.CharField(max_length=1024, null=True, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('africanlii:generic_document_detail', args=str(self.id))
