from rest_framework.serializers import (
    BooleanField,
    CharField,
    FloatField,
    IntegerField,
    ListField,
    ListSerializer,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)

from peachjam.models import DocumentTopic
from peachjam_search.models import SearchClick


class SearchableDocumentListSerializer(ListSerializer):
    def to_representation(self, data):
        self.add_topic_path_names(data)
        return super().to_representation(data)

    def add_topic_path_names(self, data):
        # add topic path names for topics that should be shown in result listings
        doc_ids = [doc.meta.id for doc in data]
        doc_topics = DocumentTopic.objects.filter(
            document_id__in=doc_ids, topic__show_in_document_listing=True
        ).prefetch_related("topic")
        topics = {}
        for doc_topic in doc_topics:
            topics.setdefault(str(doc_topic.document_id), []).append(
                doc_topic.topic.path_name
            )

        for hit in data:
            hit.topic_path_names = topics.get(hit.meta.id, [])


class SearchableDocumentSerializer(Serializer):
    id = CharField(source="meta.id")
    doc_type = CharField()
    title = CharField()
    date = CharField()
    year = IntegerField()
    jurisdiction = CharField()
    locality = CharField()
    citation = CharField()
    expression_frbr_uri = CharField()
    work_frbr_uri = CharField()
    authors = ListField()
    matter_type = CharField()
    created_at = CharField()
    case_number = ListField()
    judges = ListField()
    is_most_recent = BooleanField()
    alternative_names = ListField()
    labels = ListField()
    topic_path_names = ListField()
    _score = FloatField(source="meta.score")
    _index = CharField(source="meta.index")

    nature = SerializerMethodField()
    court = SerializerMethodField()
    highlight = SerializerMethodField()
    pages = SerializerMethodField()
    provisions = SerializerMethodField()
    content_chunks = SerializerMethodField()
    outcome = SerializerMethodField()
    registry = SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: uncomment this when we have reindexed
        # self.language_suffix = "_" + get_language_from_request(self.context["request"])
        self.language_suffix = ""

    class Meta:
        list_serializer_class = SearchableDocumentListSerializer

    def get_highlight(self, obj):
        if hasattr(obj.meta, "highlight"):
            return obj.meta.highlight.__dict__["_d_"]
        return {}

    def get_pages(self, obj):
        """Serialize nested page hits and highlights."""
        pages = []
        if hasattr(obj.meta, "inner_hits") and hasattr(obj.meta.inner_hits, "pages"):
            for page in obj.meta.inner_hits.pages.hits.hits:
                info = page._source.to_dict()
                info["highlight"] = (
                    page.highlight.to_dict() if hasattr(page, "highlight") else {}
                )
                self.merge_exact_highlights(info["highlight"])
                pages.append(info)
        return pages

    def get_provisions(self, obj):
        """Serialize nested provision hits and highlights."""
        provisions = []
        # keep track of which provisions (including parents) we've seen, so that we don't, for
        # example, repeat Chapter 7 if Chapter 7, Section 32 is also a hit
        seen = set()
        if hasattr(obj.meta, "inner_hits") and hasattr(
            obj.meta.inner_hits, "provisions"
        ):
            for provision in obj.meta.inner_hits.provisions.hits.hits:
                info = provision._source.to_dict()

                if info["id"] in seen:
                    continue
                seen.add(info["id"])
                seen.update(info["parent_ids"])

                info["highlight"] = (
                    provision.highlight.to_dict()
                    if hasattr(provision, "highlight")
                    else {}
                )
                self.merge_exact_highlights(info["highlight"])
                provisions.append(info)
        return provisions

    def get_content_chunks(self, obj):
        """Serialize content chunks from knn search."""
        chunks = []
        if hasattr(obj.meta, "inner_hits") and hasattr(
            obj.meta.inner_hits, "content_chunks"
        ):
            for chunk in obj.meta.inner_hits.content_chunks.hits.hits:
                chunks.append(chunk._source.to_dict())
        return chunks

    def get_court(self, obj):
        return obj["court" + self.language_suffix]

    def get_nature(self, obj):
        return obj["nature" + self.language_suffix]

    def get_outcome(self, obj):
        if hasattr(obj, "outcome" + self.language_suffix):
            val = obj["outcome" + self.language_suffix]
            if val is not None:
                val = list(val)
            return val
        return None

    def get_registry(self, obj):
        return obj["registry" + self.language_suffix]

    def merge_exact_highlights(self, highlight):
        # fold .exact highlights into the main field to make life easier for the client
        for key, value in list(highlight.items()):
            if key.endswith(".exact"):
                short = key[:-6]
                if short not in highlight:
                    highlight[short] = value
                del highlight[key]


class SearchClickSerializer(ModelSerializer):
    class Meta:
        model = SearchClick
        fields = ("frbr_uri", "search_trace", "portion", "position")
