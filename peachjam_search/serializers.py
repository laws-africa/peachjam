from django_elasticsearch_dsl_drf.serializers import DocumentSerializer

from peachjam_search.documents import JudgmentDocument


class JudgmentSerializer(DocumentSerializer):
    class Meta:
        document = JudgmentDocument
        fields = [
            "id",
            "title",
            "date",
            "author",
            "country",
            "citation",
            "matter_type",
            "document_content",
            "source_url",
        ]
