from django.contrib import admin

from africanlii.models import (
  AuthoringBody,
  CoreDocument,
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
  SourceFile
) 

admin.site.register([
  AuthoringBody,
  CoreDocument,
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
  SourceFile
])

