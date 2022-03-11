from django.contrib import admin
from peach_jam.models import (
  Decision, 
  MatterType, 
  Court,
)

admin.site.register(Decision)
admin.site.register(MatterType)
admin.site.register(Court)
