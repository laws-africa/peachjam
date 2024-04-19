from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework.serializers import CharField, FloatField, SerializerMethodField

from peachjam_search.documents import SearchableDocument


class SearchableDocumentSerializer(DocumentSerializer):
    id = CharField(source="meta.id")
    highlight = SerializerMethodField()
    pages = SerializerMethodField()
    provisions = SerializerMethodField()
    court = SerializerMethodField()
    nature = SerializerMethodField()
    order_outcome = SerializerMethodField()
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
        if hasattr(obj.meta, "inner_hits"):
            for page in obj.meta.inner_hits.pages.hits.hits:
                info = page._source.to_dict()
                info["highlight"] = (
                    page.highlight.to_dict() if hasattr(page, "highlight") else {}
                )
                pages.append(info)
        return pages

    def get_provisions(self, obj):
        """Serialize nested provision hits and highlights."""
        provisions = []
        if hasattr(obj.meta, "inner_hits"):
            for provision in obj.meta.inner_hits.provisions.hits.hits:
                info = provision._source.to_dict()
                info["highlight"] = (
                    provision.highlight.to_dict()
                    if hasattr(provision, "highlight")
                    else {}
                )
                provisions.append(info)
        return provisions

    def get_court(self, obj):
        return obj["court" + self.language_suffix]

    def get_nature(self, obj):
        return obj["nature" + self.language_suffix]

    def get_order_outcome(self, obj):
        val = obj["order_outcome" + self.language_suffix]
        if val is not None:
            val = list(val)
        return val

    def get_registry(self, obj):
        return obj["registry" + self.language_suffix]
