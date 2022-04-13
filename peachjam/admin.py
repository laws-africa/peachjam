from django.contrib import admin

from peachjam.models import Image, Locality, SourceFile

admin.site.register(
    [
        Image,
        Locality,
    ]
)


class SourceFileInline(admin.TabularInline):
    model = SourceFile


class CoreDocumentAdmin(admin.ModelAdmin):
    inlines = [
        SourceFileInline,
    ]
