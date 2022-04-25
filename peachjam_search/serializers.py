from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from peachjam_search.documents import SearchableDocument


class SearchableDocumentSerializer(DocumentSerializer):
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
            "content_html",
            "expression_frbr_uri",
            "work_frbr_uri",
            "authoring_body",
            "nature",
            "matter_type",
            "case_number_string",
            "court",
            "headnote_holding",
            "flynote",
            "judges"
        ]
