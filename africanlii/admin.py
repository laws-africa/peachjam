from django.contrib import admin
from peachjam.models import SourceFile

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

admin.site.register([
    AuthoringBody,
    Court,
    DocumentNature,
    Judge,
    JudgmentMediaSummaryFile,
    MatterType,
])


class SourceFileInline(admin.TabularInline):
    model = SourceFile
    extra = 0


class DocumentAdmin(admin.ModelAdmin):
    inlines = [SourceFileInline]
    list_display = ('title', 'date')
    search_fields = ('title', 'date')


admin.site.register(GenericDocument, DocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, DocumentAdmin)
