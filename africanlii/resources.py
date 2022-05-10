import logging
import mimetypes

import magic
from cobalt import FrbrUri
from countries_plus.models import Country
from django.core.files.base import File
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from languages_plus.models import Language

from africanlii.models import (
    AuthoringBody,
    Court,
    DocumentNature,
    GenericDocument,
    Judge,
    Judgment,
    MatterType,
)
from peachjam.models import Locality, SourceFile

from .download import download_source_file

logger = logging.getLogger(__name__)


class JurisdictionWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return self.model.objects.get(iso__iexact=value)
        return None


class BaseDocumentResource(resources.ModelResource):
    language = fields.Field(
        attribute="language",
        widget=ForeignKeyWidget(Language, field="iso_639_3"),
    )
    jurisdiction = fields.Field(
        attribute="jurisdiction", widget=JurisdictionWidget(Country)
    )
    locality = fields.Field(
        attribute="locality", widget=ForeignKeyWidget(Locality, field="code")
    )

    class Meta:
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "source_file",
            "coredocument_ptr",
            "doc_type",
        )
        import_id_fields = ("expression_frbr_uri",)

    def before_import_row(self, row, **kwargs):
        frbr_uri = FrbrUri.parse(row["work_frbr_uri"])
        row["language"] = frbr_uri.default_language
        row["jurisdiction"] = frbr_uri.country
        row["locality"] = frbr_uri.locality
        logger.info(f"Importing row: {row}")

    def after_save_instance(self, instance, using_transactions, dry_run):
        if not dry_run:
            if instance.source_url:
                source_file = download_source_file(instance.source_url)
                if source_file:
                    mime = magic.from_file(source_file.name, mime=True)
                    file_ext = mimetypes.guess_extension(mime)
                    SourceFile.objects.update_or_create(
                        document=instance,
                        defaults={
                            "file": File(
                                source_file, name=f"{instance.title[-250:]}{file_ext}"
                            ),
                            "mimetype": mime,
                        },
                    )


class GenericDocumentResource(BaseDocumentResource):
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

    class Meta(BaseDocumentResource.Meta):
        model = GenericDocument

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        DocumentNature.objects.get_or_create(name=row["nature"])
        AuthoringBody.objects.get_or_create(name=row["authoring_body"])


class JudgmentResource(BaseDocumentResource):
    court = fields.Field(
        column_name="court",
        attribute="court",
        widget=ForeignKeyWidget(Court, field="name"),
    )
    matter_type = fields.Field(
        column_name="matter_type",
        attribute="matter_type",
        widget=ForeignKeyWidget(MatterType, field="name"),
    )
    judges = fields.Field(
        column_name="judges",
        attribute="judges",
        widget=ManyToManyWidget(Judge, field="name"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = Judgment

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        MatterType.objects.get_or_create(name=row["matter_type"])
        Court.objects.get_or_create(
            name=row["court"],
            country=Country.objects.get(iso__iexact=row["jurisdiction"]),
        )
        if row["judges"]:
            for judge in list(map(str.strip, row["judges"].split(","))):
                Judge.objects.get_or_create(name=judge)
