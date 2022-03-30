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
  SourceFile
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

@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
  def save_model(self, request, obj, form, change):
    if change is False:
      file = obj.file
      obj.file = None
      super().save_model(request, obj, form, change)
      obj.file = file
      super().save_model(request, obj, form, change)
    else:
      super().save_model(request, obj, form, change)
