import logging
import mimetypes

import magic
from cobalt import FrbrUri
from countries_plus.models import Country
from django.core.files.base import File
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from languages_plus.models import Language

from peachjam.models import (
    Author,
    CaseNumber,
    DocumentNature,
    GenericDocument,
    Judge,
    Judgment,
    Locality,
    MatterType,
    SourceFile,
    Work,
)

from .download import download_source_file

logger = logging.getLogger(__name__)


class JurisdictionWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return self.model.objects.get(iso__iexact=value)
        return None


class BaseDocumentResource(resources.ModelResource):
    author = fields.Field(
        column_name="author",
        attribute="author",
        widget=ForeignKeyWidget(Author, field="code"),
    )
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

        work, _ = Work.objects.update_or_create(
            frbr_uri=frbr_uri, defaults={"title": row["title"]}
        )
        row["work"] = work.id
        row["author"] = row["author_obj"]["code"]

        Author.objects.get_or_create(
            code=row["author_obj"]["code"],
            name=row["author_obj"]["name"],
        )

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


class JudgmentResource(BaseDocumentResource):
    judges = fields.Field(
        column_name="judges",
        attribute="judges",
        widget=ManyToManyWidget(Judge, field="name"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = Judgment

    def before_import_row(self, row, **kwargs):
        # super().before_import_row(row, **kwargs)
        if row["judges"]:
            for judge in list(map(str.strip, row["judges"].split("|"))):
                Judge.objects.get_or_create(name=judge)

    def after_import_row(self, row, row_result, row_number=None, **kwargs):
        super().after_import_row(row, row_result, row_number, **kwargs)
        for case_number in row["case_numbers"]:
            if case_number["number"]:
                MatterType.objects.get_or_create(name=case_number["matter_type"])
                CaseNumber.objects.create(
                    document=Judgment.objects.get(pk=row_result.object_id),
                    number=case_number["number"],
                    year=case_number["year"],
                    matter_type=MatterType.objects.get(name=case_number["matter_type"]),
                )
