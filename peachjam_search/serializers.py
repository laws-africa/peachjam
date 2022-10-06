from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework.serializers import SerializerMethodField

from peachjam_search.documents import SearchableDocument


class SearchableDocumentSerializer(DocumentSerializer):
    highlight = SerializerMethodField()
    pages = SerializerMethodField()

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
                info["highlight"] = page.highlight.to_dict()
                pages.append(info)
        return pages
