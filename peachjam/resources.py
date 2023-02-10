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
from docpipe.soffice import SOfficeError, soffice_convert
from import_export import fields, resources
from import_export.widgets import (
    BooleanWidget,
    CharWidget,
    ForeignKeyWidget,
    ManyToManyWidget,
)
from languages_plus.models import Language

from peachjam.models import (
    AlternativeName,
    AttachedFileNature,
    AttachedFiles,
    Author,
    CaseNumber,
    Court,
    DocumentNature,
    DocumentTopic,
    GenericDocument,
    Judge,
    Judgment,
    Locality,
    MatterType,
    SourceFile,
    Taxonomy,
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
                    # ensure contents is on disk, because the work below reads the file data from the file name
                    file.flush()
                    file.seek(0)

                    mime = magic.from_file(file.name, mime=True)
                    if mime == "application/pdf":
                        pdf_to_text(file.name)

                    elif mime in DOC_MIMETYPES:
                        suffix = splitext(file.name)[1].lstrip(".")
                        soffice_convert(file, suffix, "html")
            return value
        except (
            requests.exceptions.RequestException,
            CalledProcessError,
            SOfficeError,
            KeyError,
        ) as e:
            msg = getattr(e, "message", repr(e)) or repr(e)
            logger.warning(
                f"Error processing source file: {source_url} -- {msg}", exc_info=e
            )
            raise ValidationError(
                f"Error processing source file: {source_url} -- {msg}"
            )

    @staticmethod
    def get_source_url(value):
        source_files = [x.strip() for x in value.split("|")]

        docx = re.compile(r"\.docx?$")
        rtf = re.compile(r"\.rtf$")
        pdf = re.compile(r"\.pdf$")

        docx_urls = []
        rtf_urls = []
        pdf_urls = []

        for file in source_files:
            match_docx = docx.search(file)
            match_rtf = rtf.search(file)
            match_pdf = pdf.search(file)
            if match_docx:
                docx_urls.append(file)
            elif match_rtf:
                rtf_urls.append(file)
            elif match_pdf:
                pdf_urls.append(file)

        if docx_urls:
            return docx_urls[0]
        if rtf_urls:
            return rtf_urls[0]
        if pdf_urls:
            return pdf_urls[0]

        return source_files[0]


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


class TaxonomiesWidget(CharWidget):
    def clean(self, value, row=None, *args, **kwargs):
        for taxonomy in value.split("|"):
            try:
                Taxonomy.objects.get(slug=taxonomy)
            except Taxonomy.DoesNotExist as e:
                msg = getattr(e, "message", repr(e)) or repr(e)
                raise ValidationError(
                    f"Taxonomy {taxonomy} does not exist - {msg}",
                )
        return value


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
    taxonomy = fields.Field(attribute="taxonomy", widget=TaxonomiesWidget())
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

        # clear out rows with 'skip' set; we don't remove them, so that the row numbers match the source, but
        # instead set all the columns (except skipped) to None
        try:
            ix = dataset.headers.index("skip")
            for i, skipped in enumerate(dataset.get_col(ix)):
                if skipped:
                    row = [None] * dataset.width
                    row[ix] = skipped
                    dataset[i] = row
        except ValueError:
            pass

    @staticmethod
    def download_attachment(url, document, nature):
        try:
            file = download_source_file(url)
            mime, _ = mimetypes.guess_type(url)
            ext = mimetypes.guess_extension(mime)
            (
                file_nature,
                _,
            ) = AttachedFileNature.objects.get_or_create(name=nature)

            AttachedFiles.objects.update_or_create(
                document=document,
                defaults={
                    "file": File(
                        file,
                        name=f"{slugify(document.title[-250:])}{ext}",
                    ),
                    "nature": file_nature,
                    "mimetype": mime,
                },
            )
        except requests.exceptions.RequestException:
            return

    def before_import_row(self, row, **kwargs):
        logger.info(f"Importing row: {row}")

    def skip_row(self, instance, original, row, import_validation_errors=None):
        return row["skip"]

    def after_import_row(self, row, row_result, row_number=None, **kwargs):
        if row.get("taxonomy"):
            for taxonomy in row.get("taxonomy").split("|"):
                taxonomy = Taxonomy.objects.get(slug=taxonomy)
                topic = DocumentTopic.objects.get_or_create(
                    topic=taxonomy, document_id=row_result.object_id
                )
                logger.info(f"Setting document topic - {topic}")

    def after_save_instance(self, instance, using_transactions, dry_run):
        # get the preferred source url using the widget logic
        source_url = SourceFileWidget.get_source_url(instance.source_url)

        if not dry_run:
            if source_url:
                logger.info(f"Downloading Source file => {source_url}")
                source_file = download_source_file(source_url)
                if source_file:
                    mime, _ = mimetypes.guess_type(source_url)
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
                # check if there are other source urls after removing the one above
                attachment_urls = instance.source_url.split("|")

                for url in attachment_urls:
                    if url == source_url:
                        continue
                    logger.info(f"Downloading Attachment => {url}")
                    self.download_attachment(url, instance, "Other documents")

            # try to extract content from docx files
            instance.extract_content_from_source_file()
            instance.source_url = source_url
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
        values = []
        keys = []

        if row.get("case_number_numeric"):
            case_number_numeric = [
                int(float(n)) for n in str(row["case_number_numeric"]).split("|")
            ]
            values.append(case_number_numeric)
            keys.append("number")

        if row.get("case_number_year"):
            case_number_year = [
                int(float(n)) for n in str(row["case_number_year"]).split("|")
            ]
            values.append(case_number_year)
            keys.append("year")

        if row.get("case_string_override"):
            case_string_override = str(row["case_string_override"]).split("|")
            values.append(case_string_override)
            keys.append("string_override")

        if row.get("matter_type"):
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

            if row.get("alternative_names"):
                for alt_citation in str(row["alternative_names"]).split("|"):
                    obj, _ = AlternativeName.objects.get_or_create(
                        document=judgment, title=alt_citation
                    )

            if row.get("media_summary_file"):
                self.download_attachment(
                    row["media_summary_file"], judgment, "Media summary"
                )
