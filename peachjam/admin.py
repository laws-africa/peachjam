from django.contrib import admin
from peachjam.models import (
  Decision, 
  MatterType, 
  Court,
)

admin.site.register(Decision)
admin.site.register(MatterType)
admin.site.register(Court)
