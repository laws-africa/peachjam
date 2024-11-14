from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework.serializers import (
    CharField,
    FloatField,
    ModelSerializer,
    SerializerMethodField,
)

from peachjam_search.documents import SearchableDocument
from peachjam_search.models import SearchClick


class SearchableDocumentSerializer(DocumentSerializer):
    id = CharField(source="meta.id")
    highlight = SerializerMethodField()
    pages = SerializerMethodField()
    provisions = SerializerMethodField()
    court = SerializerMethodField()
    nature = SerializerMethodField()
    outcome = SerializerMethodField()
    registry = SerializerMethodField()
    labels = CharField(allow_null=True)
    _score = FloatField(source="meta.score")
    _index = CharField(source="meta.index")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: uncomment this when we have reindexed
        # self.language_suffix = "_" + get_language_from_request(self.context["request"])
        self.language_suffix = ""

    class Meta:
        document = SearchableDocument
        fields = [
            "id",
            "doc_type",
            "title",
            "date",
            "year",
            "jurisdiction",
            "locality",
            "citation",
            "expression_frbr_uri",
            "work_frbr_uri",
            "author",
            "nature",
            "matter_type",
            "created_at",
            "case_number_string",
            "court",
            "judges",
            "highlight",
            "is_most_recent",
            "alternative_names",
            "labels",
            "_score",
            "_index",
        ]

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
