from tempfile import NamedTemporaryFile

from django.conf import settings
from django.utils.functional import classproperty
from django_elasticsearch_dsl import Document, Text, fields
from django_elasticsearch_dsl.registries import registry
from docpipe.pdf import pdf_to_text
from lxml import etree

from peachjam.models import CoreDocument


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
    is_most_recent = fields.BooleanField()
    created_at = fields.DateField()
    updated_at = fields.DateField()

    # Judgment
    matter_type = fields.KeywordField(attr="matter_type.name")
    case_number_string = fields.KeywordField()
    court = fields.KeywordField(attr="court.name")
    headnote_holding = fields.TextField()
    flynote = fields.TextField()
    judges = fields.TextField()

    # GenericDocument, LegalInstrument
    author = fields.KeywordField(attr="author.name")
    nature = fields.KeywordField(attr="nature.name")

    pages = fields.NestedField(
        properties={
            "page_num": fields.IntegerField(),
            "body": fields.TextField(analyzer="standard", fields={"exact": Text()}),
        }
    )

    class Index:
        name = settings.PEACHJAM["ES_INDEX"]

    class Django:
        # Because CoreDocument's default manager is a polymorphic manager, the actual instances
        # that will be prepared for searching will be subclasses of CoreDocument (eg. Judgment, etc.)
        model = CoreDocument

        @classproperty
        def related_models(cls):
            # to ensure the CoreDocument will be re-saved when subclass models are updated
            # recursively find subclasses
            def related(klass):
                res = []
                for subclass in klass.__subclasses__():
                    res.append(subclass)
                    res.extend(related(subclass))
                return res

            return related(CoreDocument)

    def get_instances_from_related(self, related_instance):
        """Retrieve the CoreDocument instance from the related instance to ensure it is re-indexed
        when the related instance is updated.
        """
        # if this extends CoreDocument, update it
        if isinstance(related_instance, CoreDocument):
            return related_instance

    def prepare_doc_type(self, instance):
        return instance.get_doc_type_display()

    def prepare_judges(self, instance):
        if instance.doc_type == "judgment":
            return [j.name for j in instance.judges.all()]

    def prepare_content(self, instance):
        if instance.content_html:
            root = etree.HTML(instance.content_html)
            return " ".join(root.itertext())

    def prepare_pages(self, instance):
        """Extract pages from PDF"""
        if not instance.content_html:
            if hasattr(
                instance, "source_file"
            ) and instance.source_file.filename.endswith(".pdf"):
                # get the file
                with NamedTemporaryFile(suffix=".pdf") as f:
                    f.write(instance.source_file.file.read())
                    f.flush()
                    text = pdf_to_text(f.name)

                if not text:
                    raise ValueError(
                        f"Couldn't index any text to search in the pdf for {instance}"
                    )
                page_texts = text.split("\x0c")
                pages = []
                for i, page in enumerate(page_texts):
                    i = i + 1
                    page = page.strip()
                    if page:
                        pages.append({"page_num": i, "body": page})
                return pages
