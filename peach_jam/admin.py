from django.contrib import admin
from peach_jam.models import (
  Decision, 
  MatterType, 
  Court,
  Country
)

admin.site.register(Decision)
admin.site.register(MatterType)
admin.site.register(Court)
admin.site.register(Country)
