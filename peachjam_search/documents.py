import copy
import logging

from django.conf import settings
from django.utils.functional import classproperty
from django_elasticsearch_dsl import Document, Text, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import RankFeature, token_filter
from elasticsearch_dsl.analysis import CustomAnalyzer

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
    Outcome,
    Taxonomy,
)
from peachjam.xmlutils import parse_html_str

log = logging.getLogger(__name__)


# the languages that translated fields support, that will be indexed into ES
# TODO: where should this language list be configured? they are languages that the interface is translated into
TRANSLATED_FIELD_LANGS = ["en", "fr", "pt", "sw"]


class RankField(fields.DEDField, RankFeature):
    pass


@registry.register_document
class SearchableDocument(Document):
    # NB: This is a legacy field; use nature for an accurate human-friendly value. This field is a mixture of doc_type
    # and nature unless the search index has been updated since nature became required.
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
    labels = fields.KeywordField()

    # Judgment
    court = fields.KeywordField(attr="court.name")
    court_en = fields.KeywordField()
    court_sw = fields.KeywordField()
    court_fr = fields.KeywordField()
    court_pt = fields.KeywordField()

    matter_type = fields.KeywordField(attr="matter_type.name")
    case_number = fields.TextField()
    # this case party names etc. and so the standard analyzer is better than a language-based one
    case_name = fields.TextField(analyzer="standard")
    case_summary = fields.TextField()
    flynote = fields.TextField()
    order = fields.TextField()
    judges = fields.KeywordField()
    judges_text = fields.TextField()
    attorneys = fields.KeywordField(attr="attorney.name")

    registry = fields.KeywordField(attr="registry.name")
    registry_en = fields.KeywordField()
    registry_sw = fields.KeywordField()
    registry_fr = fields.KeywordField()
    registry_pt = fields.KeywordField()

    outcome = fields.KeywordField()
    outcome_en = fields.KeywordField()
    outcome_sw = fields.KeywordField()
    outcome_fr = fields.KeywordField()
    outcome_pt = fields.KeywordField()

    # GenericDocument
    authors = fields.KeywordField()

    nature = fields.KeywordField(attr="nature.name")
    nature_en = fields.KeywordField()
    nature_sw = fields.KeywordField()
    nature_fr = fields.KeywordField()
    nature_pt = fields.KeywordField()

    ranking = RankField(attr="work.ranking")
    # a negative boost to search results; this must be a positive number, but is treated as a penalty
    # it is applied linearly, simply reducing the score by this amount
    penalty = RankField(attr="search_penalty", positive_score_impact=False)

    pages = fields.NestedField(
        properties={
            "page_num": fields.IntegerField(),
            "body": fields.TextField(fields={"exact": Text()}),
        }
    )

    provisions = fields.NestedField(
        properties={
            "title": fields.TextField(),
            "id": fields.KeywordField(),
            "num": fields.KeywordField(),
            "type": fields.KeywordField(),
            "parent_titles": fields.TextField(),
            "parent_ids": fields.KeywordField(),
            "body": fields.TextField(fields={"exact": Text()}),
        }
    )

    # for typeahead suggestions
    suggest = fields.CompletionField(analyzer="standard")

    # this will be used to build prepare_xxx_xx fields for each of these
    translated_fields = [
        ("court", "name"),
        ("registry", "name"),
        ("nature", "name"),
    ]

    # ES's max request size is 100mb, so limit the size of the text fields to a little below that
    # 80 MB
    MAX_TEXT_LENGTH = 80 * 1024 * 1024

    def should_index_object(self, obj):
        if isinstance(obj, ExternalDocument) or not obj.published:
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
                Outcome,
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

        if any(isinstance(related_instance, cls) for cls in [CourtRegistry, Outcome]):
            return related_instance.judgments.all()

        if any(isinstance(related_instance, cls) for cls in [Court, Judge, Attorney]):
            return related_instance.judgment_set.all()

        if isinstance(related_instance, Author):
            return CoreDocument.objects.filter(
                genericdocument__authors=related_instance
            )

        if isinstance(related_instance, Taxonomy):
            topics = [related_instance] + [
                t for t in related_instance.get_descendants()
            ]
            return CoreDocument.objects.filter(taxonomies__topic__in=topics).distinct()

    def prepare_case_number(self, instance):
        if hasattr(instance, "case_numbers"):
            return [c.get_case_number_string() for c in instance.case_numbers.all()]

    def prepare_alternative_names(self, instance):
        return [a.title for a in instance.alternative_names.all()]

    def prepare_judges(self, instance):
        if instance.doc_type == "judgment":
            return [j.name for j in instance.judges.all()]

    def prepare_judges_text(self, instance):
        return self.prepare_judges(instance)

    def prepare_attorneys(self, instance):
        if instance.doc_type == "judgment":
            return [a.name for a in instance.attorneys.all()]

    def prepare_authors(self, instance):
        if hasattr(instance, "author"):
            return [a.name for a in instance.author_list]

    def prepare_content(self, instance):
        """Text content of document body for non-PDFs."""
        if instance.content_html and (
            not instance.content_html_is_akn or not instance.toc_json
        ):
            text = instance.get_content_as_text()
            if text and len(text) > self.MAX_TEXT_LENGTH:
                log.warning(
                    f"Limiting text content of {instance} to {self.MAX_TEXT_LENGTH} (length is {len(text)})"
                )
                text = text[: self.MAX_TEXT_LENGTH]
            return text

    def prepare_ranking(self, instance):
        if instance.work.ranking > 0:
            return instance.work.ranking
        return 0.00000001

    def prepare_court(self, instance):
        if hasattr(instance, "court") and instance.court:
            return instance.court.name

    def prepare_registry(self, instance):
        if hasattr(instance, "registry") and instance.registry:
            return instance.registry.name

    def prepare_outcome(self, instance):
        if hasattr(instance, "outcomes") and instance.outcomes:
            return [outcome.name for outcome in instance.outcomes.all()]

    def prepare_outcome_en(self, instance):
        return get_translated_m2m_name(instance, "outcomes", "en")

    def prepare_outcome_fr(self, instance):
        return get_translated_m2m_name(instance, "outcomes", "fr")

    def prepare_outcome_pt(self, instance):
        return get_translated_m2m_name(instance, "outcomes", "pt")

    def prepare_outcome_sw(self, instance):
        return get_translated_m2m_name(instance, "outcomes", "sw")

    def prepare_pages(self, instance):
        """Text content of pages extracted from PDF."""
        if not instance.content_html:
            text = instance.get_content_as_text()
            if text and len(text) > self.MAX_TEXT_LENGTH:
                log.warning(
                    f"Limiting text content of {instance} to {self.MAX_TEXT_LENGTH} (length is {len(text)})"
                )
                text = text[: self.MAX_TEXT_LENGTH]
            page_texts = text.split("\x0c")
            pages = []
            for i, page in enumerate(page_texts):
                i = i + 1
                page = page.strip()
                if page:
                    pages.append({"page_num": i, "body": page})
            return pages

    def prepare_provisions(self, instance):
        """Text content of provisions from AKN HTML."""

        def prepare_provision(item, parents):
            provision = None
            provision_id = item["id"] or item["type"]

            # get the text of the provision
            body = []
            for provision_el in root.xpath(f'//*[@id="{provision_id}"]'):
                for el in provision_el:
                    # exclude headings so they aren't indexed twice
                    if el.tag not in ["h1", "h2", "h3", "h4", "h5"]:
                        body.append(" ".join(el.itertext()))
                break
            if body:
                provision = {
                    "title": item["title"],
                    "id": provision_id,
                    "num": (item["num"] or "").rstrip("."),
                    "type": item["type"],
                    "parent_titles": [
                        p["title"] for p in parents if p["title"] and p["id"]
                    ],
                    "parent_ids": [p["id"] for p in parents if p["title"] and p["id"]],
                    "body": " ".join(body),
                }
                provisions.append(provision)

            # recurse into children
            if not item["basic_unit"]:
                if provision:
                    parents = parents + [provision]
                for child in item["children"] or []:
                    prepare_provision(child, parents)

        if instance.content_html and instance.content_html_is_akn and instance.toc_json:
            # index each provision separately
            provisions = []
            root = parse_html_str(instance.content_html)
            for item in instance.toc_json:
                prepare_provision(item, [])

            return provisions

    def prepare_taxonomies(self, instance):
        """Taxonomy topics are stored as slugs of all the items in the tree down to that topic. This is easier than
        storing and querying hierarchical taxonomy entries."""
        # get all the ancestors of each topic
        topics = list(instance.taxonomies.all())
        topics = [t.topic for t in topics] + [
            a for t in topics for a in t.topic.get_ancestors()
        ]
        return list({t.slug for t in topics})

    def prepare_labels(self, instance):
        return [label.code for label in instance.labels.all()]

    def prepare_title_expanded(self, instance):
        # combination of the title, citation and alternative names
        parts = [instance.title]
        if instance.citation and instance.citation != instance.title:
            parts.append(instance.citation)
        parts.extend([a.title for a in instance.alternative_names.all()])
        return " ".join(parts)

    def prepare_suggest(self, instance):
        # don't provide suggestions for gazettes
        if instance.frbr_uri_doctype == "officialGazette":
            return None

        suggestions = [instance.title]

        if instance.citation and instance.citation != instance.title:
            suggestions.append(instance.citation)

        for name in instance.alternative_names.all():
            suggestions.append(name.title)

        return suggestions

    def _prepare_action(self, object_instance, action):
        info = super()._prepare_action(object_instance, action)
        log.info(f"Prepared document #{object_instance.pk} for indexing")
        info[
            "_index"
        ] = MultiLanguageIndexManager.get_instance().get_index_for_language(
            object_instance.language.iso_639_2T
        )
        return info

    def get_queryset(self):
        # order by pk descending so that when we're indexing we can have an idea of progress
        return super().get_queryset().order_by("-pk")


def get_translated_m2m_name(instance, field, lang):
    """Get the translated name of a many-to-many field."""
    if hasattr(instance, field) and getattr(instance, field):
        return [
            getattr(v, f"name_{lang}", None) or v.name
            for v in getattr(instance, field).all()
        ]


def prepare_translated_field(self, instance, field, attr, lang):
    if getattr(instance, field, None):
        fld = getattr(instance, field)
        attr_name = f"{attr}_{lang}"
        if hasattr(fld, attr_name):
            return getattr(fld, attr_name) or getattr(fld, attr)


def make_prepare(field, attr, lang):
    return lambda s, i: prepare_translated_field(s, i, field, attr, lang)


# add preparation methods for translated fields to avoid lots of copy-and-paste
for field, attr in SearchableDocument.translated_fields:
    for lang in TRANSLATED_FIELD_LANGS:
        # we must call make_prepare so that the variables are evaluated now, not when the function is called
        setattr(
            SearchableDocument,
            f"prepare_{field}_{lang}",
            make_prepare(field, attr, lang),
        )


class MultiLanguageIndexManager:
    """Helper that creates multi-language indexes from the main search index definition.
    and ensures the text fields use the correct language variant analyzers."""

    # These are the language-specific indexes we create and their associated analyzers for text fields.
    # Documents in other languages are stored in a general index with the "standard" analyzer
    ANALYZERS = {
        "ara": "arabic",
        "eng": "english",
        "fra": "french",
        "por": "portuguese",
    }

    # analyzer and filters for synonyms
    SEARCH_ANALYZERS = {
        # Re-implement the built-in English analyzer, but include English synonyms
        # See https://www.elastic.co/guide/en/elasticsearch/reference/7.17/analysis-lang-analyzer.html#english-analyzer
        "eng": CustomAnalyzer(
            "english_synonym",
            tokenizer="standard",
            filter=[
                token_filter(
                    "english_synonym_filter",
                    type="synonym_graph",
                    synonyms=[
                        # Any occurrence of one of these words will be expanded to all the others.
                        # All the terms will then go through the normal filters, such as lowercasing and stemming.
                        # NB: synonyms are case-sensitive
                        "Anor, Another",
                        "AU, African Union",
                        "au, African Union",
                        "delict, tort",
                        "Ors, Others",
                        "ors, others",
                        "R, Republic",
                        "S, State",
                        "v, vs, versus",
                        "V, Vs, Versus",
                    ],
                ),
                token_filter(
                    "english_possessive_stemmer",
                    type="stemmer",
                    language="possessive_english",
                ),
                "lowercase",
                token_filter("english_stop", type="stop", stopwords="_english_"),
                token_filter("english_stemmer", type="stemmer", language="english"),
            ],
        )
    }

    def __init__(self):
        self.main_index = SearchableDocument._index
        self.language_indexes = self.create_language_indexes()
        self.load_language_index_settings(from_server=False)

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    def create_language_indexes(self):
        """Create basic multi-language indexes. They are not fully configured with mapping details, because that
        requires an elasticsearch connection."""
        return {
            lang: self.main_index.clone(f"{self.main_index._name}_{lang}")
            for lang in self.ANALYZERS.keys()
        }

    def load_language_index_settings(self, from_server=True):
        """Configure mappings etc for the language indexes. Requires an elasticsearch connection."""
        main_mappings = self.main_index.to_dict()["mappings"]

        for lang, index in self.language_indexes.items():
            search_analyzer = None
            if lang in self.SEARCH_ANALYZERS:
                # setup synonyms
                index.analyzer(self.SEARCH_ANALYZERS[lang])
                search_analyzer = self.SEARCH_ANALYZERS[lang]._name

            if from_server and index.exists():
                is_new = False
                index.load_mappings()
                new_mappings = index.get_or_create_mapping().to_dict()
                # merge in new fields
                for fld in main_mappings["properties"]:
                    if fld not in new_mappings["properties"]:
                        new_mappings["properties"][fld] = main_mappings["properties"][
                            fld
                        ]
            else:
                is_new = True
                new_mappings = copy.deepcopy(main_mappings)

            # update analyzers store mappings
            self.set_text_field_analyzer(
                new_mappings["properties"],
                self.ANALYZERS[lang],
                search_analyzer,
                is_new,
            )
            index.get_or_create_mapping()._update_from_dict(new_mappings)

    def set_text_field_analyzer(self, fields, analyzer, search_analyzer, is_new):
        """Recursively set analyzers for text fields."""
        # these fields weren't initialised correctly and we can't change the mappings
        for name, fld in fields.items():
            if fld["type"] == "text":
                if is_new and "analyzer" not in fld:
                    # the analyzer can't change once it is set
                    fld["analyzer"] = analyzer

                if search_analyzer and (
                    is_new and fld.get("analyzer") == analyzer or "analyzer" not in fld
                ):
                    # this can always change
                    fld["search_analyzer"] = search_analyzer

                # the analyzer can't change once it is set
                if is_new and "analyzer" not in fld:
                    fld["analyzer"] = analyzer
            elif fld["type"] == "nested":
                self.set_text_field_analyzer(
                    fld["properties"], analyzer, search_analyzer, is_new
                )

    def update_language_index_settings(self):
        for index in self.language_indexes.values():
            log.info(f"Updating index settings for {index._name}")
            index.close()
            log.info("Index closed")
            try:
                index.save()
                log.info("Index updated")
            finally:
                index.open()
                log.info("Index re-opened")

    def register_indexes(self):
        for index in self.language_indexes.values():
            registry.register(index, SearchableDocument)

    def get_all_search_index_names(self):
        """The names of all indexes to use for a search."""
        names = [self.main_index._name] + [
            ix._name for ix in self.language_indexes.values()
        ]
        # fold in language variants of the extra search indexes, if any
        return names + [
            f"{i}_{lang}"
            for i in settings.PEACHJAM["EXTRA_SEARCH_INDEXES"]
            for lang in self.ANALYZERS.keys()
        ]

    def get_index_for_language(self, lang):
        if lang in self.ANALYZERS:
            return f"{self.main_index._name}_{lang}"
        return self.main_index._name
