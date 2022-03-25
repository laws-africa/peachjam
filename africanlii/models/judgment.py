from django.db import models
from django.urls import reverse
from .matter_type import MatterType
from .core_document_model import CoreDocumentModel
from .court import Court
from .judge import Judge

class Judgment(CoreDocumentModel):
    """ This model represents judgments it inherits from the CoreDocumentModel.
    """
   
    case_number_numeric = models.CharField(max_length=1024, null=True, blank=True)
    case_number_year = models.IntegerField(null=True, blank=True)
    case_number_string = models.CharField(max_length=1024, null=True, blank=True)

    matter_type = models.ForeignKey(MatterType, on_delete=models.PROTECT, null=True, blank=True)

    court = models.ForeignKey(Court, on_delete=models.PROTECT, null=True, blank=True)
    judges = models.ManyToManyField(Judge, blank=True)

    headnote_holding = models.TextField(blank=True)
    additional_citations = models.TextField(blank=True)

    media_summary_file = models.FileField(upload_to='judgments/media_summary/', null=True, blank=True)

    flynote = models.TextField(blank=True)


    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.case_number_string = self.get_case_number_string()
        return super().save(*args, **kwargs)

    def get_case_number_string(self):
        return f'{self.matter_type} {self.case_number_numeric} of {self.case_number_year}'

    def get_absolute_url(self):
        return reverse('africanlii:judgment_detail', args=str(self.id))
