import logging
import mimetypes
import re

import magic
import requests.exceptions
from cobalt import FrbrUri
from countries_plus.models import Country
from django.core.files.base import File
from django.forms import ValidationError
from django.utils.text import slugify
from import_export import fields, resources
from import_export.widgets import (
    BooleanWidget,
    CharWidget,
    ForeignKeyWidget,
    ManyToManyWidget,
)
from languages_plus.models import Language

from peachjam.models import (
    AttachedFileNature,
    AttachedFiles,
    Author,
    CaseNumber,
    Court,
    DocumentNature,
    GenericDocument,
    Judge,
    Judgment,
    Locality,
    MatterType,
    SourceFile,
)

from .download import download_source_file

logger = logging.getLogger(__name__)


class JurisdictionWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return self.model.objects.get(iso__iexact=value)
        return None


class AuthorWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return self.model.objects.get(code__iexact=value)
        return None


class SourceFileWidget(CharWidget):
    def clean(self, value, row=None, **kwargs):
        try:
            r = requests.head(value)
            r.raise_for_status()
            return value
        except requests.exceptions.HTTPError as e:
            raise ValidationError(e)


class SkipRowWidget(BooleanWidget):
    def clean(self, value, row=None, **kwargs):
        return bool(value)


class BaseDocumentResource(resources.ModelResource):
    author = fields.Field(
        column_name="author",
        attribute="author",
        widget=AuthorWidget(Author),
    )
    language = fields.Field(
        attribute="language",
        widget=ForeignKeyWidget(Language, field="iso_639_2T"),
    )
    jurisdiction = fields.Field(
        attribute="jurisdiction", widget=JurisdictionWidget(Country)
    )
    locality = fields.Field(
        attribute="locality", widget=ForeignKeyWidget(Locality, field="code")
    )
    source_url = fields.Field(attribute="source_url", widget=SourceFileWidget())
    skip = fields.Field(attribute="skip", widget=SkipRowWidget())

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
        row["frbr_uri_number"] = frbr_uri.number
        row["frbr_uri_doctype"] = frbr_uri.doctype
        row["frbr_uri_subtype"] = frbr_uri.subtype
        row["frbr_uri_date"] = frbr_uri.date

        if frbr_uri.actor:
            row["frbr_uri_actor"] = frbr_uri.actor
            row["author"] = frbr_uri.actor

        logger.info(f"Importing row: {row}")

    def skip_row(self, instance, original, row, import_validation_errors=None):
        return row["skip"]

    def after_save_instance(self, instance, using_transactions, dry_run):
        if not dry_run:
            if instance.source_url:
                source_file = download_source_file(instance.source_url)
                if source_file:
                    mime = magic.from_file(source_file.name, mime=True)

                    if mime == "application/zip":
                        mime, _ = mimetypes.guess_type(instance.source_url)

                    file_ext = mimetypes.guess_extension(mime)
                    SourceFile.objects.update_or_create(
                        document=instance,
                        defaults={
                            "file": File(
                                source_file,
                                name=f"{slugify(instance.title[-250:])}{file_ext}",
                            ),
                            "mimetype": mime,
                        },
                    )

            # try to extract content from docx files
            if not instance.content_html:
                instance.extract_content_from_source_file()

            # extract citations
            instance.extract_citations()
            instance.save()


class DocumentNatureWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        nature, _ = self.model.objects.get_or_create(
            code=value, defaults={"name": value}
        )
        return nature


class GenericDocumentResource(BaseDocumentResource):
    nature = fields.Field(
        column_name="nature",
        attribute="nature",
        widget=DocumentNatureWidget(DocumentNature, field="code"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = GenericDocument

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)


class JudgesWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):

        # Remove extra white space around and in between the judges names
        judges = [" ".join(j.split()) for j in value.split(self.separator)]

        for j in judges:
            judge, _ = self.model.objects.get_or_create(name=j)
        return self.model.objects.filter(name__in=judges)


class JudgmentResource(BaseDocumentResource):
    judges = fields.Field(
        column_name="judges",
        attribute="judges",
        widget=JudgesWidget(Judge, separator="|", field="name"),
    )
    court = fields.Field(
        column_name="court",
        attribute="court",
        widget=ForeignKeyWidget(Court, field="code"),
    )
    case_numbers = fields.Field(column_name="case_numbers", widget=CharWidget)

    class Meta(BaseDocumentResource.Meta):
        model = Judgment

    @staticmethod
    def get_case_numbers(row):

        case_number_numeric = [int(n) for n in row["case_number_numeric"].split("|")]
        case_number_year = row["case_number_year"].split("|")
        case_string_override = row["case_string_override"].split("|")
        values = [case_number_numeric, case_number_year, case_string_override]
        keys = ["number", "year", "string_override"]

        if row["matter_type"]:
            matter_type = row["matter_type"].split("|")
            matter_types = [
                MatterType.objects.get_or_create(name=m)[0] for m in matter_type
            ]
            keys.append("matter_type")
            values.append(matter_types)

        combined_data = zip(*values)
        case_numbers_data = [
            {k: v for (k, v) in zip(keys, data)} for data in combined_data
        ]
        case_numbers = [CaseNumber(**data) for data in case_numbers_data]

        return case_numbers

    @staticmethod
    def get_source_url(row):
        source_url = None
        source_files = [x.strip() for x in row["source_url"].split("|")]
        docx = re.compile(r"\.docx?$")
        pdf = re.compile(r"\.pdf$")
        for file in source_files:
            match_docx = docx.search(file)
            match_pdf = pdf.search(file)
            # prefer the .docx file if available, otherwise use .pdf, ignore .rtf
            if match_docx:
                source_url = file
                break
            elif match_pdf:
                source_url = file

        return source_url

    def before_import_row(self, row, **kwargs):
        logger.info(f"Importing row: {row}")
        row["source_url"] = self.get_source_url(row)

    def after_import_row(self, row, instance, row_number=None, **kwargs):
        super().after_import_row(row, instance, row_number, **kwargs)

        judgment = Judgment.objects.get(pk=instance.object_id)

        for case_number in self.get_case_numbers(row):
            case_number.document = judgment
            case_number.save()

        judgment.save()

        if row["media_summary_file"]:
            summary_file = download_source_file(row["media_summary_file"])
            mime, _ = mimetypes.guess_type(row["media_summary_file"])
            ext = mimetypes.guess_extension(mime)
            media_summary_file_nature, _ = AttachedFileNature.objects.get_or_create(
                name="Media summary"
            )

            AttachedFiles.objects.update_or_create(
                document=judgment,
                defaults={
                    "file": File(
                        summary_file, name=f"{slugify(judgment.title[-250:])}{ext}"
                    ),
                    "nature": media_summary_file_nature,
                    "mimetype": mime,
                },
            )
