from django.db import models
from languages_plus.models import Language
from countries_plus.models import Country
from .images import ImageSet
from .locality import Locality


class CoreDocumentModel(models.Model):
  """ 
  This is the abstact document model that has fields that are
  common to most documents.
  """
  title = models.CharField(max_length=1024, null=False, blank=False)
  date = models.DateField(null=False, blank=False)
  source_url = models.URLField(max_length=2048, null=True, blank=True)
  source_file = models.FileField(null=True, blank=True)
  citation = models.CharField(max_length=1024, null=True, blank=True)
  content_html = models.TextField(null=True, blank=True)
  images = models.OneToOneField(ImageSet, on_delete=models.PROTECT, blank=True, null=True)
  language = models.ForeignKey(Language, on_delete=models.PROTECT, null=True, blank=True)
  jurisdicition = models.ForeignKey(Country, on_delete=models.PROTECT, null=True, blank=True)
  locality = models.ForeignKey(Locality, on_delete=models.PROTECT, null=True, blank=True)
  expression_frbr_uri = models.CharField(max_length=1024, null=True, blank=True)
  work_frbr_uri = models.CharField(max_length=1024, null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    abstract = True
