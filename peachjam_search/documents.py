from django.conf import settings
from django_elasticsearch_dsl import Document, Text, fields
from django_elasticsearch_dsl.registries import registry
from docpipe.pdf import pdf_to_text
from lxml import etree

from peachjam.models import (
    CoreDocument,
    GenericDocument,
    Judgment,
    LegalInstrument,
    Legislation,
)


@registry.register_document
class SearchableDocument(Document):
    doc_type = fields.KeywordField()
    title = fields.TextField()
    date = fields.DateField()
    year = fields.KeywordField(attr="date.year")
    citation = fields.TextField()
    content = fields.TextField()
    language = fields.KeywordField(attr="language.name_native")
    jurisdiction = fields.KeywordField(attr="jurisdiction.name")
    locality = fields.KeywordField(attr="locality.name")
    expression_frbr_uri = fields.KeywordField()
    work_frbr_uri = fields.KeywordField()
    created_at = fields.DateField()
    updated_at = fields.DateField()

    # Judgment
    matter_type = fields.KeywordField(attr="judgment.matter_type.name")
    case_number_string = fields.KeywordField(attr="judgment.case_number_string")
    court = fields.KeywordField(attr="judgment.court.name")
    headnote_holding = fields.TextField(attr="judgment.headnote_holding")
    flynote = fields.TextField(attr="judgment.flynote")
    judges = fields.TextField()

    # GenericDocument, LegalInstrument
    author = fields.KeywordField()
    nature = fields.KeywordField()

    pages = fields.NestedField(
        properties={
            "page_num": fields.IntegerField(),
            "body": fields.TextField(analyzer="standard", fields={"exact": Text()}),
        }
    )

    class Index:
        # TODO: make this configurable per website
        name = settings.PEACHJAM["ES_INDEX"]

    class Django:
        model = CoreDocument
        # to ensure the CoreDocument will be re-saved when Judgment, Legislation etc is updated
        related_models = [GenericDocument, Judgment, LegalInstrument, Legislation]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related(
                "judgment", "legalinstrument", "legislation", "genericdocument"
            )
        )

    def get_instances_from_related(self, related_instance):
        """Retrieve the CoreDocument instance from the related instance to ensure it is re-indexed
        when the related instance is updated.
        """
        if isinstance(
            related_instance, (GenericDocument, Judgment, LegalInstrument, Legislation)
        ):
            return related_instance.coredocument_ptr

    def prepare_doc_type(self, instance):
        return instance.get_doc_type_display()

    def prepare_authoring_body(self, instance):
        if instance.doc_type == "generic_document":
            return instance.genericdocument.author.name
        elif instance.doc_type == "legal_instrument":
            return instance.legalinstrument.author.name

    def prepare_nature(self, instance):
        if instance.doc_type == "generic_document":
            return instance.genericdocument.nature.name
        elif instance.doc_type == "legal_instrument":
            return instance.legalinstrument.nature.name

    def prepare_judges(self, instance):
        if instance.doc_type == "judgment":
            return [j.name for j in instance.judgment.judges.all()]

    def prepare_content(self, instance):
        if instance.content_html:
            root = etree.HTML(instance.content_html)
            return " ".join(root.itertext())

    def prepare_pages(self, instance):
        """Extract pages from PDF"""
        if hasattr(instance, "source_file") and instance.source_file.filename.endswith(
            ".pdf"
        ):
            text = pdf_to_text(instance.source_file.file.path)

            if not text:
                raise ValueError(
                    f"Couldn't any text to search for the pdf text for {instance}"
                )
            page_texts = text.split("\x0c")
            pages = []
            for i, page in enumerate(page_texts):
                i = i + 1
                page = page.strip()
                if page:
                    pages.append({"page_num": i, "body": page})
            return pages
