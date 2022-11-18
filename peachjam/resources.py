import logging
import mimetypes
import re
from datetime import datetime
from os.path import splitext
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile, TemporaryDirectory

import magic
import requests.exceptions
from cobalt import FrbrUri
from countries_plus.models import Country
from dateutil.parser import parse
from django.core.files.base import File
from django.forms import ValidationError
from django.utils.text import slugify
from docpipe.pdf import pdf_to_text
from docpipe.soffice import soffice_convert
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
from peachjam.pipelines import DOC_MIMETYPES

from .download import download_source_file

logger = logging.getLogger(__name__)


class CharRequiredWidget(CharWidget):
    def __init__(self, field):
        self.field = field

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValidationError(f"{self.field} is required")
        return value


class ForeignKeyRequiredWidget(ForeignKeyWidget):
    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name

    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValidationError(f"{self.name} is required")
        return self.model.objects.get(**{self.field: value})


class SourceFileWidget(CharRequiredWidget):
    def clean(self, value, row=None, **kwargs):
        super().clean(value)
        source_url = self.get_source_url(value)
        try:
            with TemporaryDirectory() as dir:
                with NamedTemporaryFile(dir=dir) as file:
                    response = requests.get(source_url)
                    response.raise_for_status()
                    file.write(response.content)
                    file.seek(0)

                    mime = magic.from_file(file.name, mime=True)
                    if mime == "application/pdf":
                        pdf_to_text(file.name)

                    elif mime in DOC_MIMETYPES:
                        suffix = splitext(file.name)[1].lstrip(".")
                        soffice_convert(file, suffix, "html")
            return source_url
        except (
            requests.exceptions.RequestException,
            CalledProcessError,
            KeyError,
        ) as e:
            raise ValidationError(f"Error processing source file: {e}")

    @staticmethod
    def get_source_url(value):
        source_url = None
        source_files = [x.strip() for x in value.split("|")]
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


class SkipRowWidget(BooleanWidget):
    def clean(self, value, row=None, **kwargs):
        return bool(value)


class AuthorWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValidationError("author is required")
        return self.model.objects.get(code__iexact=value)


class DateWidget(CharWidget):
    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name

    def clean(self, value, row=None, name=None, *args, **kwargs):
        if self.name == "date" and value is None:
            raise ValidationError("Date is required")

        if value:
            if type(value) == datetime:
                return value
            return parse(value)


class BaseDocumentResource(resources.ModelResource):
    date = fields.Field(attribute="date", widget=DateWidget(name="date"))

    author = fields.Field(
        attribute="author",
        widget=AuthorWidget(Author),
    )
    language = fields.Field(
        attribute="language",
        widget=ForeignKeyRequiredWidget(Language, name="language", field="iso_639_2T"),
    )
    jurisdiction = fields.Field(
        attribute="jurisdiction",
        widget=ForeignKeyRequiredWidget(Country, name="jurisdiction", field="iso"),
    )
    locality = fields.Field(
        attribute="locality",
        widget=ForeignKeyRequiredWidget(Locality, name="locality", field="code"),
    )
    source_url = fields.Field(
        attribute="source_url", widget=SourceFileWidget(field="source_url")
    )
    skip = fields.Field(attribute="skip", widget=SkipRowWidget())

    required_fields = []

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

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):

        dataset_headers = dataset.headers
        missing_fields = set(self.required_fields).difference(dataset_headers)

        if missing_fields:
            raise ValidationError(f"Missing Columns: {missing_fields}")

    def before_import_row(self, row, **kwargs):
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

    required_fields = (
        "author",
        "date",
        "jurisdiction",
        "language",
        "nature",
        "source_url",
        "title",
        "work_frbr_uri",
    )

    class Meta(BaseDocumentResource.Meta):
        model = GenericDocument

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        frbr_uri = FrbrUri.parse(row["work_frbr_uri"])
        row["language"] = frbr_uri.default_language
        row["jurisdiction"] = str(frbr_uri.country).upper()
        row["locality"] = frbr_uri.locality
        row["frbr_uri_number"] = frbr_uri.number
        row["frbr_uri_doctype"] = frbr_uri.doctype
        row["frbr_uri_subtype"] = frbr_uri.subtype
        row["frbr_uri_date"] = frbr_uri.date

        if frbr_uri.actor:
            row["frbr_uri_actor"] = frbr_uri.actor
            row["author"] = frbr_uri.actor


class JudgesWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):

        # Remove extra white space around and in between the judges names
        if value:
            judges = [" ".join(j.split()) for j in value.split(self.separator)]

            for j in judges:
                judge, _ = self.model.objects.get_or_create(name=j)
            return self.model.objects.filter(name__in=judges)
        return []


class JudgmentResource(BaseDocumentResource):
    hearing_date = fields.Field(
        attribute="hearing_date", widget=DateWidget(name="hearing_date")
    )
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

    required_fields = (
        "case_name",
        "court",
        "date",
        "judges",
        "jurisdiction",
        "language",
        "source_url",
    )

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

    def after_import_row(self, row, instance, row_number=None, **kwargs):
        super().after_import_row(row, instance, row_number, **kwargs)

        judgment = Judgment.objects.filter(pk=instance.object_id).first()

        if judgment:
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
