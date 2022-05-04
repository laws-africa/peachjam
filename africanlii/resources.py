import mimetypes
import re

import magic
from cobalt import FrbrUri
from countries_plus.models import Country
from django.core.files.base import File
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget
from languages_plus.models import Language

from africanlii.models import AuthoringBody, DocumentNature, GenericDocument, Judgment
from peachjam.models import Locality, SourceFile

from .google import download_file_from_google


class BaseDocumentResource(resources.ModelResource):
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
        # model = GenericDocument
        exclude = (
            "id",
            "created_at",
            "updated_at",
            "source_file",
            "coredocument_ptr",
        )
        import_id_fields = ("expression_frbr_uri",)

    def before_import_row(self, row, **kwargs):
        frbr_uri = FrbrUri.parse(row["work_frbr_uri"])
        row["language"] = frbr_uri.default_language
        row["jurisdiction"] = str(frbr_uri.country).upper()
        row["locality"] = frbr_uri.locality

    def after_save_instance(self, instance, using_transactions, dry_run):
        if not dry_run:
            pattern = r"(?<=document\/d\/)(?P<google_id>.*)(?=\/)"
            regex = re.compile(pattern)
            match = regex.search(instance.source_url)

            if match:
                google_id = match.group("google_id")
                temp_file = download_file_from_google(google_id)
                mime = magic.from_file(temp_file.name, mime=True)
                file_ext = mimetypes.guess_extension(mime)
                SourceFile.objects.update_or_create(
                    document=instance,
                    defaults={
                        "file": File(
                            temp_file, name=f"{instance.title[-250:]}{file_ext}"
                        ),
                        "mimetype": mime,
                    },
                )


class GenericDocumentResource(BaseDocumentResource):
    class Meta(BaseDocumentResource.Meta):
        model = GenericDocument


class JudgmentResource(BaseDocumentResource):
    class Meta(BaseDocumentResource.Meta):
        model = Judgment
