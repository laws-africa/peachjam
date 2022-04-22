from cobalt import FrbrUri
from countries_plus.models import Country
from django.contrib import admin
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget
from languages_plus.models import Language

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
from peachjam.models import Locality

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


class GenericDocumentResource(resources.ModelResource):
    authoring_body = fields.Field(
        column_name="authoring_body",
        attribute="authoring_body",
        widget=ForeignKeyWidget(AuthoringBody, field="name"),
    )
    nature = fields.Field(
        column_name="nature",
        attribute="nature",
        widget=ForeignKeyWidget(DocumentNature, field="name"),
    )
    language = fields.Field(
        column_name="language",
        attribute="language",
        widget=ForeignKeyWidget(Language, field="iso_639_3"),
    )
    jurisdiction = fields.Field(
        attribute="jurisdiction", widget=ForeignKeyWidget(Country, field="iso")
    )
    locality = fields.Field(
        attribute="locality", widget=ForeignKeyWidget(Locality, field="code")
    )

    class Meta:
        model = GenericDocument

    def import_data(self, dataset, dry_run, **kwargs):
        result = super().import_data(dataset, dry_run=True, **kwargs)
        return result

    def before_import_row(self, row, **kwargs):
        frbr_uri = FrbrUri.parse(row["work_frbr_uri"])
        row["language"] = frbr_uri.default_language
        row["jurisdiction"] = str(frbr_uri.country).upper()
        row["locality"] = frbr_uri.locality


class GenericDocumentAdmin(DocumentAdmin):
    resource_class = GenericDocumentResource


admin.site.register(GenericDocument, GenericDocumentAdmin)
admin.site.register(Legislation, DocumentAdmin)
admin.site.register(LegalInstrument, DocumentAdmin)
admin.site.register(Judgment, DocumentAdmin)
