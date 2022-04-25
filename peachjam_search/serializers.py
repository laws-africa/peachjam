from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework.serializers import SerializerMethodField

from peachjam_search.documents import SearchableDocument


class SearchableDocumentSerializer(DocumentSerializer):
    highlight = SerializerMethodField()

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
            "content",
            "expression_frbr_uri",
            "work_frbr_uri",
            "authoring_body",
            "nature",
            "matter_type",
            "case_number_string",
            "court",
            "headnote_holding",
            "flynote",
            "judges",
            "highlight",
        ]

    def get_highlight(self, obj):
        if hasattr(obj.meta, "highlight"):
            return obj.meta.highlight.__dict__["_d_"]
        return {}
