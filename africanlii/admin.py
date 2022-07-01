import copy

from django.contrib import admin
from import_export.admin import ImportMixin

from peachjam.admin import DocumentAdmin
from peachjam.models import (
    Author,
    CaseNumber,
    DocumentNature,
    GenericDocument,
    Judge,
    Judgment,
    JudgmentMediaSummaryFile,
    LegalInstrument,
    Legislation,
    MatterType,
)

from .resources import GenericDocumentResource, JudgmentResource

admin.site.register(
    [
        Author,
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
    fields = ["matter_type", "number", "year"]


class GenericDocumentAdmin(ImportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource

    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])


class LegalInstrumentAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "nature"])


class LegislationAdmin(ImportMixin, DocumentAdmin):
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[3][1]["fields"].extend(["metadata_json"])
    fieldsets[2][1]["classes"] = ("collapse",)


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    resource_class = JudgmentResource
    inlines = [CaseNumberAdmin] + DocumentAdmin.inlines
    fieldsets = copy.deepcopy(DocumentAdmin.fieldsets)
    fieldsets[0][1]["fields"].extend(["author", "judges"])
    fieldsets[2][1]["fields"].extend(
        ["headnote_holding", "additional_citations", "flynote"]
    )


admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, LegislationAdmin)
admin.site.register(LegalInstrument, LegalInstrumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)
