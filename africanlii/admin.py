from django.contrib import admin
from import_export.admin import ImportMixin

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


class GenericDocumentAdmin(ImportMixin, DocumentAdmin):
    resource_class = GenericDocumentResource


class JudgmentAdmin(ImportMixin, DocumentAdmin):
    resource_class = JudgmentResource


admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, JudgmentAdmin)
