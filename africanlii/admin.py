from django.contrib import admin

from africanlii.models import (
  Court,
  DocumentNature,
  GenericDocument,
  Image,
  Judge,
  Judgment,
  JudgmentMediaSummaryFile,
  LegalInstrument,
  Legislation,
  Locality,
  MatterType,
) 

admin.site.register([
  Court,
  DocumentNature,
  GenericDocument,
  Image,
  Judge,
  Judgment,
  JudgmentMediaSummaryFile,
  LegalInstrument,
  Legislation,
  Locality,
  MatterType,
])
