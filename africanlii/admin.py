from django.contrib import admin

from africanlii.models import Judgment, MatterType, Court


admin.site.register(Judgment)
admin.site.register(MatterType)
admin.site.register(Court)
