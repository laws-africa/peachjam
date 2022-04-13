from django.contrib import admin
from django.utils.html import format_html

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
    readonly_fields = ("filename", "mimetype", "attachment_link")

    def attachment_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{url}">{title}</a>', url=obj.file.path, title=obj.filename
            )

    attachment_link.short_description = "Attachment"


class DocumentAdmin(admin.ModelAdmin):
    inlines = [SourceFileInline]
    list_display = ("title", "date")
    search_fields = ("title", "date")
    exclude = ("doc_type",)


admin.site.register(GenericDocument, DocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, DocumentAdmin)
