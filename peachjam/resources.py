import logging
import mimetypes
import re
from datetime import datetime
from os.path import splitext
from subprocess import CalledProcessError
from tempfile import NamedTemporaryFile, TemporaryDirectory

import lxml.html
import magic
import requests.exceptions
from cobalt import FrbrUri
from countries_plus.models import Country
from dateutil.parser import parse
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.files.base import File
from django.forms import ValidationError
from django.urls import reverse
from django.utils.text import slugify
from docpipe.pdf import pdf_to_text
from docpipe.soffice import SOfficeError, soffice_convert
from import_export import fields, resources
from import_export.formats.base_formats import CSV, XLSX
from import_export.widgets import (
    BooleanWidget,
    CharWidget,
    ForeignKeyWidget,
    ManyToManyWidget,
)
from languages_plus.models import Language

from peachjam.models import (
    AlternativeName,
    Article,
    AttachedFileNature,
    AttachedFiles,
    Attorney,
    Author,
    Bill,
    CaseNumber,
    CauseList,
    CoreDocument,
    Court,
    CourtDivision,
    CourtRegistry,
    CustomProperty,
    CustomPropertyLabel,
    DocumentNature,
    DocumentTopic,
    Gazette,
    GenericDocument,
    Judge,
    Judgment,
    Label,
    Legislation,
    Locality,
    MatterType,
    Outcome,
    Ratification,
    RatificationCountry,
    SourceFile,
    Taxonomy,
    Work,
    citations_processor,
)
from peachjam.pipelines import DOC_MIMETYPES

from .download import download_source_file

logger = logging.getLogger(__name__)
User = get_user_model()


class ForeignKeyRequiredWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("this field is required")
        return super().clean(value, row, *args, **kwargs)


class SourceFileWidget(CharWidget):
    def clean(self, value, row=None, **kwargs):
        value = super().clean(value)
        if not value:
            return value

        source_url = self.get_best_source_url(value)
        source_url = source_url.replace(" ", "%20")
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
                        # retry when conversion fails
                        attempt = 0
                        while attempt <= 3:
                            file.seek(0)
                            attempt += 1
                            try:
                                logger.info(
                                    f"converting file from {source_url} to html (attempt {attempt})"
                                )
                                soffice_convert(file, suffix, "html")
                                logger.info(f"soffice success on attempt {attempt}")
                                break
                            except SOfficeError as e:
                                logger.warning(
                                    f"soffice error on attempt {attempt} of 3",
                                    exc_info=e,
                                )
                                if attempt >= 3:
                                    raise

            return source_url
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
            raise ValueError(f"Error processing source file: {source_url} -- {msg}")

    @staticmethod
    def get_best_source_url(value):
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


class DateWidget(CharWidget):
    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name

    def clean(self, value, row=None, name=None, *args, **kwargs):
        if self.name == "date" and value is None:
            raise ValueError("Date is required")

        if value:
            if type(value) == datetime:
                return value
            return parse(value)


class TaxonomiesWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()

        taxonomies = []
        for taxonomy in value.split(self.separator):
            taxonomy = taxonomy.strip()
            try:
                taxonomies.append(Taxonomy.objects.get(slug=taxonomy))
            except Taxonomy.DoesNotExist:
                raise ValueError(f"Taxonomy does not exist: {taxonomy}")

        return [self.model(**{self.field: t}) for t in taxonomies]


class CustomPropertiesWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        """Parse newline separate key: value pairs."""
        properties = []
        for prop in (value or "").strip().splitlines():
            prop = prop.strip()
            if not prop or ":" not in prop:
                continue
            key, value = prop.split(":", 1)
            if key and value:
                label = CustomPropertyLabel.objects.get_or_create(
                    name__iexact=key, defaults={"name": key}
                )[0]
                properties.append(CustomProperty(label=label, value=value.strip()))
        return properties


class ManyToManyField(fields.Field):
    """Handles many-to-many relationships."""

    def save(self, obj, data, is_m2m=False, **kwargs):
        if not self.readonly:
            attrs = self.attribute.split("__")
            for attr in attrs[:-1]:
                obj = getattr(obj, attr, None)
            cleaned = self.clean(data, **kwargs)
            if cleaned is not None or self.saves_null_values:
                assert is_m2m
                getattr(obj, attrs[-1]).all().delete()
                getattr(obj, attrs[-1]).set(cleaned, bulk=False)


class ManyToOneWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()
        values = [v.strip() for v in value.split(self.separator)]
        return [self.model(**{self.field: v}) for v in values if v]

    def render(self, value, obj=None):
        if obj.pk:
            return super().render(value, obj)


class StripHtmlWidget(CharWidget):
    def clean(self, value, row=None, **kwargs):
        value = super().clean(value)
        # possibly html?
        if value and value.startswith("<"):
            tree = lxml.html.fromstring(value)
            value = " ".join(tree.xpath("//text()")).strip()
        return value


class BaseDocumentResource(resources.ModelResource):
    frbr_uri_date = fields.Field(
        attribute="frbr_uri_date",
        widget=CharWidget(coerce_to_string=True, allow_blank=True),
    )
    date = fields.Field(attribute="date", widget=DateWidget(name="date"))
    language = fields.Field(
        attribute="language",
        widget=ForeignKeyRequiredWidget(Language, field="iso_639_2T"),
    )
    jurisdiction = fields.Field(
        attribute="jurisdiction",
        widget=ForeignKeyRequiredWidget(Country, field="iso"),
    )
    locality = fields.Field(
        attribute="locality",
        widget=ForeignKeyWidget(Locality, field="code"),
    )
    source_url = fields.Field(attribute="source_url", widget=SourceFileWidget())
    taxonomies = ManyToManyField(
        attribute="taxonomies",
        widget=TaxonomiesWidget(DocumentTopic, separator="|", field="topic"),
    )
    skip = fields.Field(attribute="skip", widget=SkipRowWidget())
    alternative_names = ManyToManyField(
        attribute="alternative_names",
        widget=ManyToOneWidget(AlternativeName, separator="|", field="title"),
    )
    custom_properties = ManyToManyField(
        attribute="custom_properties", widget=CustomPropertiesWidget(CustomProperty)
    )
    download_url = fields.Field(readonly=True)

    def get_queryset(self):
        return (
            self._meta.model.objects.get_qs_no_defer()
            .select_related("jurisdiction", "locality", "language")
            .prefetch_related("custom_properties", "taxonomies")
        )

    def dehydrate_download_url(self, obj):
        domain = Site.objects.get_current().domain
        if obj.expression_frbr_uri:
            download_source = reverse(
                "document_source", kwargs={"frbr_uri": obj.expression_frbr_uri[1:]}
            )
            scheme = "https"
            return f"{scheme}://{domain}{download_source}"
        return ""

    def dehydrate_custom_properties(self, obj):
        if obj.pk:
            return "\n".join(
                f"{prop.label.name}: {prop.value}"
                for prop in obj.custom_properties.all()
            )

    class Meta:
        exclude = (
            "updated_at",
            "source_file",
            "coredocument_ptr",
            "doc_type",
            "polymorphic_ctype",
            "work",
            "toc_json",
        )
        import_id_fields = ("expression_frbr_uri",)
        clean_model_instances = True

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
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
        # strip whitespace from all string fields
        for k, v in row.items():
            row[k] = v.strip() if isinstance(v, str) else v
        if kwargs.get("user"):
            row["created_by"] = kwargs["user"].id
        if not row.get("skip"):
            logger.info(f"Importing row: {row}")

    def skip_row(self, instance, original, row, import_validation_errors=None):
        return row["skip"] or all(not x for x in row.values())

    def after_import_instance(self, instance, new, row_number=None, **kwargs):
        instance.track_changes()

    def save_m2m(self, instance, row, using_transactions, dry_run):
        super().save_m2m(instance, row, using_transactions, dry_run)

        if not dry_run:
            # only re-extract content if the content explicitly changed, or the source file changed (next block)
            extract_content = "content_html" in row

            # attach source file, but only if it was explicitly provided during import
            # the preferred source URL was set during import by the SourceFileWidget
            if (
                instance.source_url
                and row.get("source_url")
                and instance.source_url in row.get("source_url")
            ):
                self.attach_source_file(instance, instance.source_url)
                extract_content = True

            if extract_content:
                # try to extract content from docx files
                instance.extract_content_from_source_file()
                # extract citations
                instance.extract_citations()
                instance.save()

    def after_save_instance(self, instance, using_transactions, dry_run):
        if not dry_run:
            cp = citations_processor()
            cp.queue_re_extract_citations(instance.date)

    def attach_source_file(self, instance, source_url):
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

    def dehydrate_taxonomies(self, instance):
        if instance.pk:
            return "|".join(t.topic.slug for t in instance.taxonomies.all())


class DocumentNatureWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            return self.model.objects.get_or_create(
                code=value, defaults={"name": value}
            )[0]


class ManyToManyFieldWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        # Remove extra white space around and in between the judges' or attorneys' names
        if value:
            items = [" ".join(j.split()) for j in value.split(self.separator)]

            for item in items:
                obj, _ = self.model.objects.get_or_create(**{self.field: item})

            lookup = f"{self.field}__in"
            return self.model.objects.filter(**{lookup: items})
        return []


class ManyToManyRequiredWidget(ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            items = [j for j in value.split(self.separator)]
            for item in items:
                try:
                    self.model.objects.get(**{self.field: item})
                except self.model.DoesNotExist:
                    raise ValueError(f"{item } does not exist in {self.model.__name__}")

            lookup = f"{self.field}__in"
            return self.model.objects.filter(**{lookup: items})
        return []


class GenericDocumentResource(BaseDocumentResource):
    nature = fields.Field(
        column_name="nature",
        attribute="nature",
        widget=DocumentNatureWidget(DocumentNature, field="code"),
    )
    author = fields.Field(
        column_name="author",
        attribute="author",
        widget=ManyToManyRequiredWidget(Author, separator="|", field="code"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = GenericDocument

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        if row.get("work_frbr_uri"):
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


class JudgmentResource(BaseDocumentResource):
    hearing_date = fields.Field(
        attribute="hearing_date", widget=DateWidget(name="hearing_date")
    )
    judges = fields.Field(
        column_name="judges",
        attribute="judges",
        widget=ManyToManyFieldWidget(Judge, separator="|", field="name"),
    )
    attorneys = fields.Field(
        column_name="attorneys",
        attribute="attorneys",
        widget=ManyToManyFieldWidget(Attorney, separator="|", field="name"),
    )
    court = fields.Field(
        column_name="court",
        attribute="court",
        widget=ForeignKeyRequiredWidget(Court, field="code"),
    )
    registry = fields.Field(
        column_name="registry",
        attribute="registry",
        widget=ForeignKeyWidget(CourtRegistry, field="code"),
    )
    case_number_numeric = fields.Field(
        column_name="case_number_numeric", widget=CharWidget
    )
    case_number_year = fields.Field(column_name="case_number_year", widget=CharWidget)
    case_string_override = fields.Field(
        column_name="case_string_override", widget=CharWidget
    )
    matter_type = fields.Field(column_name="matter_type", widget=CharWidget)

    outcome = fields.Field(
        column_name="outcome",
        attribute="outcome",
        widget=ForeignKeyWidget(Outcome, field="name"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = Judgment

    @staticmethod
    def get_case_numbers(row):
        values = []
        keys = []

        if row.get("case_number_numeric"):
            case_number_numeric = [
                int(float(n)) if n else None
                for n in str(row["case_number_numeric"]).split("|")
            ]
            values.append(case_number_numeric)
            keys.append("number")

        if row.get("case_number_year"):
            case_number_year = [
                int(float(n)) if n else None
                for n in str(row["case_number_year"]).split("|")
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
                MatterType.objects.get_or_create(name=m)[0]
                for m in matter_type
                if m.strip()
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
            CaseNumber.objects.filter(document=judgment).delete()
            for case_number in self.get_case_numbers(row):
                case_number.document = judgment
                case_number.save()

            judgment.save()

            if row.get("media_summary_file"):
                self.download_attachment(
                    row["media_summary_file"], judgment, "Media summary"
                )

    def get_case_number_attributes(self, judgment, attribute):
        values = []
        if judgment.pk:
            for case_number in judgment.case_numbers.all().order_by(
                "year", "number", "string_override"
            ):
                val = getattr(case_number, attribute)
                values.append(f"{val or ''}")

        return "|".join(values)

    def dehydrate_case_number_numeric(self, judgment):
        return self.get_case_number_attributes(judgment, "number")

    def dehydrate_case_number_year(self, judgment):
        return self.get_case_number_attributes(judgment, "year")

    def dehydrate_case_string_override(self, judgment):
        return self.get_case_number_attributes(judgment, "string_override")

    def dehydrate_matter_type(self, judgment):
        values = []
        if judgment.pk:
            for case_number in judgment.case_numbers.all().order_by(
                "year", "number", "string_override"
            ):
                if getattr(case_number, "matter_type"):
                    values.append(case_number.matter_type.name)
                else:
                    values.append("")

        return "|".join(values)


class ArticleAuthorWidget(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("author is required")
        parts = value.split(None, 1)
        author, _ = self.model.objects.get_or_create(
            username=slugify(value),
            defaults={
                "first_name": parts[0] if parts else "",
                "last_name": parts[1] if len(parts) > 1 else "",
            },
        )

        return author


class ImageWidget(CharWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if value:
            try:
                file_url = value
                file = download_source_file(file_url)
                mime, _ = mimetypes.guess_type(file_url)
                file_ext = mimetypes.guess_extension(mime)
                return File(file, name=f"{slugify(value[:20])}{file_ext}")
            except requests.exceptions.RequestException as e:
                msg = getattr(e, "message", repr(e)) or repr(e)
                logger.warning(f"Error downloading image: {value} - {msg}")
                raise ValidationError(f"Error downloading image: {value} - {msg}")


class PublishedWidget(BooleanWidget):
    def clean(self, value, row=None, **kwargs):
        return bool(value)


class TopicsWidget(ManyToManyWidget):
    def clean(self, value, row=None, **kwargs):
        if value:
            article_tag_root = Article.get_article_tags_root()

            taxonomies = [
                " ".join(t.split()).capitalize() for t in value.split(self.separator)
            ]
            for taxonomy in taxonomies:
                topic = Taxonomy.objects.filter(name__iexact=taxonomy).first()
                if not topic:
                    article_tag_root.add_child(name=taxonomy)
            return Taxonomy.objects.filter(name__in=taxonomies)
        return []


class ArticleResource(resources.ModelResource):
    author = fields.Field(
        column_name="author",
        attribute="author",
        widget=ArticleAuthorWidget(User, field="username"),
    )
    image = fields.Field(attribute="image", column_name="image", widget=ImageWidget())
    published = fields.Field(
        attribute="published", column_name="published", widget=PublishedWidget()
    )
    topics = fields.Field(
        column_name="topics",
        attribute="topics",
        widget=TopicsWidget(Taxonomy, separator=","),
    )
    summary = fields.Field(
        column_name="summary",
        attribute="summary",
        widget=StripHtmlWidget(),
    )

    class Meta:
        model = Article
        exclude = ("slug",)


class GazetteResource(BaseDocumentResource):
    class Meta(BaseDocumentResource.Meta):
        model = Gazette


class UserResource(resources.ModelResource):
    groups = fields.Field(
        column_name="groups",
        attribute="groups",
        widget=ManyToManyFieldWidget(Group, separator="|", field="name"),
    )

    class Meta:
        model = User
        exclude = ("id",)
        import_id_fields = ("email", "username")
        # export_order = ("first_name", "last_name", "email", "groups")

    def before_save_instance(self, instance, using_transactions, dry_run):
        if not instance.pk:
            instance.username = instance.email
            instance.password = make_password(instance.password)
            instance.is_staff = True
            instance.save()


class AttorneyResource(resources.ModelResource):
    description = fields.Field(
        column_name="description",
        attribute="description",
        widget=CharWidget(),
        default="",
    )

    class Meta:
        model = Attorney


class RatificationField(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("work frbr_uri is required")
        work = Work.objects.filter(frbr_uri=value).first()
        if not work:
            raise ValueError(f'work with frbr_uri "{value}" not found')
        ratification = Ratification.objects.update_or_create(
            work=work,
            defaults={
                "source_url": row.get("source_url"),
                "last_updated": row.get("last_updated"),
            },
        )[0]
        return ratification


class CountryField(ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            raise ValueError("country code is required")
        country = Country.objects.filter(iso=value.upper()).first()
        if not country:
            raise ValueError(f'country with iso "{value}" not found')
        return country


class RatificationResource(resources.ModelResource):
    work = fields.Field(
        column_name="work",
        attribute="ratification",
        widget=RatificationField(Ratification, field="work__frbr_uri"),
    )
    country = fields.Field(
        attribute="country",
        column_name="country",
        widget=CountryField(Country, field="pk"),
    )
    ratification_date = fields.Field(
        attribute="ratification_date",
        column_name="ratification_date",
        widget=DateWidget(),
    )
    deposit_date = fields.Field(
        attribute="deposit_date",
        column_name="deposit_date",
        widget=DateWidget(),
    )
    signature_date = fields.Field(
        attribute="signature_date",
        column_name="signature_date",
        widget=DateWidget(),
    )
    source_url = fields.Field(
        attribute="ratification__source_url",
        column_name="source_url",
        widget=CharWidget(),
    )
    last_updated = fields.Field(
        attribute="ratification__last_updated",
        column_name="last_updated",
        widget=DateWidget(),
    )

    class Meta:
        model = RatificationCountry
        exclude = ("id", "ratification")
        import_id_fields = (
            "work",
            "country",
        )

    def filter_export(self, queryset, *args, **kwargs):
        return RatificationCountry.objects.filter(
            ratification__in=queryset
        ).select_related("country", "ratification", "ratification__work")


class BillResource(BaseDocumentResource):
    author = fields.Field(
        column_name="author",
        attribute="author",
        widget=ForeignKeyWidget(Author, field="code"),
    )

    class Meta(BaseDocumentResource.Meta):
        model = Bill


class DownloadDocumentsResource(resources.ModelResource):
    """Resource used for downloading collections of documents by users from search results and saved folders."""

    download_formats = {
        "xlsx": XLSX,
        "csv": CSV,
    }

    # all documents
    nature = fields.Field("nature")
    title = fields.Field("title")
    date = fields.Field("date", widget=DateWidget())
    citation = fields.Field("citation")
    url = fields.Field(readonly=True)
    source_url = fields.Field(readonly=True)
    expression_frbr_uri = fields.Field("expression_frbr_uri")
    language = fields.Field("language")
    jurisdiction = fields.Field("jurisdiction")
    locality = fields.Field("locality")
    labels = fields.Field(
        "labels", widget=ManyToManyWidget(Label, separator=", ", field="name")
    )

    # judgments
    court = fields.Field("court", widget=DateWidget())
    registry = fields.Field("registry", widget=DateWidget())
    order = fields.Field("order")
    judges = fields.Field(
        "judges", widget=ManyToManyWidget(Judge, separator=", ", field="name")
    )

    # generic documents
    author = fields.Field(
        "author", widget=ManyToManyWidget(Author, separator=", ", field="name")
    )

    # causelists
    division = fields.Field(
        "division", widget=ManyToManyWidget(CourtDivision, separator=", ", field="name")
    )

    # legislation
    repealed = fields.Field("repealed")
    principal = fields.Field("principal")
    commenced = fields.Field("commenced")
    parent_work = fields.Field(
        "parent_work", widget=ForeignKeyWidget(Work, field="frbr_uri")
    )

    # FK fields above must be added to either select_related or prefetch_related
    select_related = {
        None: ["language", "nature", "jurisdiction", "locality"],
        CauseList: ["court", "registry", "division"],
        Judgment: ["court", "registry"],
        Legislation: ["parent_work"],
    }
    prefetch_related = {
        None: ["labels"],
        CauseList: ["judges"],
        GenericDocument: ["author"],
        Judgment: ["judges"],
    }

    def dehydrate_url(self, obj):
        domain = Site.objects.get_current().domain
        if obj.expression_frbr_uri:
            return f"https://{domain}{obj.expression_frbr_uri}"
        return ""

    def dehydrate_source_url(self, obj):
        domain = Site.objects.get_current().domain
        if obj.expression_frbr_uri:
            download_source = reverse(
                "document_source", kwargs={"frbr_uri": obj.expression_frbr_uri[1:]}
            )
            return f"https://{domain}{download_source}"
        return ""

    @classmethod
    def get_objects_for_download(cls, pks):
        """Helper method to return a list of documents identified by the provided PKs, ready for download with this
        resource. This ensures correct prefetches to make the export more efficient."""
        # group pks by content type
        by_ctype = {}
        qs = (
            CoreDocument.objects.non_polymorphic()
            .filter(pk__in=pks)
            .select_related("polymorphic_ctype")
            .only("pk", "polymorphic_ctype")
        )
        for doc in qs:
            by_ctype.setdefault(doc.polymorphic_ctype, []).append(doc.pk)

        # load each type separately with the correct prefetches
        docs = []
        for ctype, ctype_pks in by_ctype.items():
            model = ctype.model_class()
            qs = model.objects.filter(pk__in=ctype_pks)
            qs = qs.select_related(
                *(cls.select_related.get(model) or [] + cls.select_related[None])
            )
            qs = qs.prefetch_related(
                *(cls.prefetch_related.get(model) or [] + cls.prefetch_related[None])
            )
            docs.extend(qs.all())

        # sort docs based on the initial order of pks
        docs = sorted(docs, key=lambda d: pks.index(d.pk))

        return docs
