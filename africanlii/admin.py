from django.contrib import admin
from import_export.admin import ImportMixin

from africanlii.models import (
    AuthoringBody,
    CaseNumber,
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
from peachjam.admin import DocumentAdmin

from .resources import GenericDocumentResource, JudgmentResource

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


class CaseNumberAdmin(admin.TabularInline):
    model = CaseNumber
    extra = 1
    verbose_name = "Case number"
    verbose_name_plural = "Case numbers"
    readonly_fields = ["string"]


class GenericDocumentAdmin(ImportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    resource_class = JudgmentResource
    inlines = [CaseNumberAdmin] + DocumentAdmin.inlines


admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)
