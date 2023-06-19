import copy
import logging

from django.conf import settings
from django.utils.functional import classproperty
from django_elasticsearch_dsl import Document, Text, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import RankFeature
from elasticsearch_dsl.index import Index

from peachjam.models import (
    Attorney,
    Author,
    CoreDocument,
    Court,
    CourtRegistry,
    DocumentNature,
    ExternalDocument,
    Judge,
    Locality,
    OrderOutcome,
    Taxonomy,
)

log = logging.getLogger(__name__)


class RankField(fields.DEDField, RankFeature):
    pass


@registry.register_document
class SearchableDocument(Document):
    doc_type = fields.KeywordField()
    title = fields.TextField()
    # title field for sorting and alphabetical listing
    title_keyword = fields.KeywordField(attr="title")
    # title and citations combined to allow searching that overlaps those fields
    title_expanded = fields.TextField()
    date = fields.DateField()
    year = fields.KeywordField(attr="date.year")
    citation = fields.TextField()
    mnc = fields.TextField()
    content = fields.TextField()
    language = fields.KeywordField(attr="language.name_native")
    jurisdiction = fields.KeywordField(attr="jurisdiction.name")
    locality = fields.KeywordField(attr="locality.name")
    expression_frbr_uri = fields.KeywordField()
    work_frbr_uri = fields.KeywordField()
    is_most_recent = fields.BooleanField()
    alternative_names = fields.TextField()
    created_at = fields.DateField()
    updated_at = fields.DateField()
    taxonomies = fields.KeywordField()

    # Judgment
    matter_type = fields.KeywordField(attr="matter_type.name")
    case_number = fields.TextField()
    court = fields.KeywordField(attr="court.name")
    headnote_holding = fields.TextField()
    flynote = fields.TextField()
    judges = fields.KeywordField(attr="judge.name")
    registry = fields.KeywordField(attr="registry.name")
    attorneys = fields.KeywordField(attr="attorney.name")
    order_outcome = fields.KeywordField(attr="order_outcome.name")

    # GenericDocument, LegalInstrument
    authors = fields.KeywordField()
    nature = fields.KeywordField(attr="nature.name")

    ranking = RankField(attr="work.ranking")

    pages = fields.NestedField(
        properties={
            "page_num": fields.IntegerField(),
            "body": fields.TextField(analyzer="standard", fields={"exact": Text()}),
        }
    )

    def should_index_object(self, obj):
        if isinstance(obj, ExternalDocument):
            return False
        return True

    class Index:
        name = settings.PEACHJAM["ES_INDEX"]
        settings = {"index.mapping.nested_objects.limit": 50000}

    class Django:
        # Because CoreDocument's default manager is a polymorphic manager, the actual instances
        # that will be prepared for searching will be subclasses of CoreDocument (eg. Judgment, etc.)
        model = CoreDocument
        # indexing queryset.enumerate chunk size
        queryset_pagination = 100

        @classproperty
        def related_models(cls):

            # to ensure the CoreDocument will be re-saved when subclass models are updated
            # recursively find subclasses
            def get_subclasses(klass):
                res = []
                for subclass in klass.__subclasses__():
                    res.append(subclass)
                    res.extend(get_subclasses(subclass))
                return res

            subclasses = get_subclasses(CoreDocument)

            # add related models
            related_models = [
                Locality,
                Court,
                CourtRegistry,
                OrderOutcome,
                Author,
                Judge,
                Attorney,
                DocumentNature,
                Taxonomy,
            ]

            return subclasses + related_models

    def get_instances_from_related(self, related_instance):
        """Retrieve the CoreDocument instance from the related instance to ensure it is re-indexed
        when the related instance is updated.
        """
        # if this extends CoreDocument, update it
        if isinstance(related_instance, CoreDocument):
            return related_instance

        # for all related models we get the CoreDocument instances
        if any(isinstance(related_instance, cls) for cls in [Locality, DocumentNature]):
            return related_instance.coredocument_set.all()

        if any(
            isinstance(related_instance, cls) for cls in [CourtRegistry, OrderOutcome]
        ):
            return related_instance.judgments.all()

        if any(isinstance(related_instance, cls) for cls in [Court, Judge, Attorney]):
            return related_instance.judgment_set.all()

        if isinstance(related_instance, Author):
            generic = CoreDocument.objects.filter(
                genericdocument__authors=related_instance
            )
            legal = CoreDocument.objects.filter(
                legalinstrument__authors=related_instance
            )
            return generic | legal

        if isinstance(related_instance, Taxonomy):
            topics = [related_instance] + [
                t for t in related_instance.get_descendants()
            ]
            return CoreDocument.objects.filter(taxonomies__topic__in=topics).distinct()

    def prepare_doc_type(self, instance):
        return instance.get_doc_type_display()

    def prepare_citation(self, instance):
        # if there is no citation, fall back to the title so as not to penalise documents that don't have a citation
        return instance.citation or instance.title

    def prepare_case_number(self, instance):
        if hasattr(instance, "case_numbers"):
            return [c.get_case_number_string() for c in instance.case_numbers.all()]

    def prepare_alternative_names(self, instance):
        return [a.title for a in instance.alternative_names.all()]

    def prepare_judges(self, instance):
        if instance.doc_type == "judgment":
            return [j.name for j in instance.judges.all()]

    def prepare_attorneys(self, instance):
        if instance.doc_type == "judgment":
            return [a.name for a in instance.attorneys.all()]

    def prepare_authors(self, instance):
        if hasattr(instance, "authors"):
            return [a.name for a in instance.authors.all()]

    def prepare_content(self, instance):
        """Text content of document body for non-PDFs."""
        if instance.content_html:
            return instance.get_content_as_text()

    def prepare_ranking(self, instance):
        if instance.work.ranking > 0:
            return instance.work.ranking
        return 0.00000001

    def prepare_pages(self, instance):
        """Text content of pages extracted from PDF."""
        if not instance.content_html:
            if hasattr(
                instance, "source_file"
            ) and instance.source_file.filename.endswith(".pdf"):
                text = instance.get_content_as_text()
                page_texts = text.split("\x0c")
                pages = []
                for i, page in enumerate(page_texts):
                    i = i + 1
                    page = page.strip()
                    if page:
                        pages.append({"page_num": i, "body": page})
                return pages

    def prepare_taxonomies(self, instance):
        """Taxonomy topics are stored as slugs of all the items in the tree down to that topic. This is easier than
        storing and querying hierarchical taxonomy entries."""
        # get all the ancestors of each topic
        topics = list(instance.taxonomies.all())
        topics = [t.topic for t in topics] + [
            a for t in topics for a in t.topic.get_ancestors()
        ]
        return list({t.slug for t in topics})

    def prepare_title_expanded(self, instance):
        # combination of the title, citation and alternative names
        parts = [instance.title]
        if instance.citation and instance.citation != instance.title:
            parts.append(instance.citation)
        parts.extend([a.title for a in instance.alternative_names.all()])
        return " ".join(parts)

    def get_index_for_language(self, lang):
        if lang in ANALYZERS:
            return f"{self._index._name}_{lang}"
        return self._index._name

    def _prepare_action(self, object_instance, action):
        info = super()._prepare_action(object_instance, action)
        log.info(f"Prepared document #{object_instance.pk} for indexing")
        info["_index"] = self.get_index_for_language(
            object_instance.language.iso_639_2T
        )
        return info

    def get_queryset(self):
        # order by pk descending so that when we're indexing we can have an idea of progress
        return super().get_queryset().order_by("-pk")


# These are the language-specific indexes we create and their associated analyzers for text fields.
# Documents in other languages are stored in a general index with the "standard" analyzer
ANALYZERS = {
    "ara": "arabic",
    "eng": "english",
    "fra": "french",
    "por": "portuguese",
}


def get_search_indexes(base_index):
    return (
        [base_index]
        + [f"{base_index}_{lang}" for lang in ANALYZERS.keys()]
        + [
            f"{i}_{lang}"
            for i in settings.EXTRA_SEARCH_INDEXES
            for lang in ANALYZERS.keys()
        ]
    )


def setup_language_indexes():
    """Setup multi-language indexes."""
    main_index = SearchableDocument._index
    mappings = main_index.to_dict()["mappings"]

    def set_analyzer(fields, analyzer):
        """Recursively set analyzer for text fields."""
        for fld in fields:
            if fld["type"] == "text":
                fld["analyzer"] = analyzer
            elif fld["type"] == "nested":
                set_analyzer(fld["properties"].values(), analyzer)

    for lang, analyzer in ANALYZERS.items():
        new_mappings = copy.deepcopy(mappings)
        set_analyzer(new_mappings["properties"].values(), analyzer)
        index = Index(name=f"{main_index._name}_{lang}")
        index.get_or_create_mapping()._update_from_dict(new_mappings)
        index._settings = main_index._settings
        registry.register(index, SearchableDocument)
