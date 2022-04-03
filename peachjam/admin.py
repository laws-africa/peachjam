from django.contrib import admin
from peachjam.models import (
    CoreDocument,
    Image,
    SourceFile,
    Locality,
)

admin.site.register([
    Image,
    Locality,
])


class SourceFileInline(admin.TabularInline):
    model = SourceFile


class CoreDocumentAdmin(admin.ModelAdmin):
    inlines = [
        SourceFileInline,
    ]

# admin.site.register(CoreDocument, CoreDocumentAdmin)
