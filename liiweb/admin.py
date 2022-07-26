from django.contrib import admin

from liiweb.models import CourtClass, CourtDetail


class CourtClassAdmin(admin.ModelAdmin):
    list_display = ["name", "description"]


class CourtDetailAdmin(admin.ModelAdmin):
    list_display = ["court", "court_class"]


admin.site.register(CourtClass, CourtClassAdmin)
admin.site.register(CourtDetail, CourtDetailAdmin)
