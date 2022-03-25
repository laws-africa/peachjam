from django.db import models
from django.urls import reverse
from .core_document_model import CoreDocumentModel

class Legislation(CoreDocumentModel):
    """ 
    This model represents legal instruments.
    """
    toc_json = models.JSONField(null=True, blank=True) 
    metadata_json = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('africanlii:legislation_detail', args=str(self.id))
