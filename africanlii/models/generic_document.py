from django.db import models
from .core_document_model import CoreDocumentModel

class GenericDocument(CoreDocumentModel):
    """ 
    This model represents generic documents.
    """
    nature = models.CharField(max_length=1024, null=True, blank=True)
    author = models.CharField(max_length=1024, null=True, blank=True)
