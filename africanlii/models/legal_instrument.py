from django.db import models
from .core_document_model import CoreDocumentModel
from .authoring_body import AuthoringBody
from .document_nature import DocumentNature

class LegalInstrument(CoreDocumentModel):
    """ 
    This model represents legal instruments.
    """
    author = models.ForeignKey(AuthoringBody, on_delete=models.PROTECT, null=True, blank=True)
    nature = models.ForeignKey(DocumentNature, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return self.title
