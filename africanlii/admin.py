from django.contrib import admin

from africanlii.models import (
    AuthoringBody,
    Court,
    DocumentNature,
    GenericDocument,
    Judge,
    Judgment,
    JudgmentMediaSummaryFile,
    LegalInstrument,
    Legislation,
    MatterType,
)
from peachjam.models import SourceFile

admin.site.register(
    [
        AuthoringBody,
        Court,
        DocumentNature,
        Judge,
        JudgmentMediaSummaryFile,
        MatterType,
    ]
)


class SourceFileInline(admin.TabularInline):
    model = SourceFile
    extra = 0
    exclude = ("filename", "mimetype")


class DocumentAdmin(admin.ModelAdmin):
    inlines = [SourceFileInline]
    list_display = ("title", "date")
    search_fields = ("title", "date")
    exclude = ("doc_type",)


admin.site.register(GenericDocument, DocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, DocumentAdmin)
