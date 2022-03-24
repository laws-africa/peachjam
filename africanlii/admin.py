from django.contrib import admin

from africanlii.models import (
  Court,
  DocumentNature,
  GenericDocument,
  Image,
  ImageSet,
  Judge,
  Judgment,
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
  ImageSet,
  Judge,
  Judgment,
  LegalInstrument,
  Legislation,
  Locality,
  MatterType,
])
