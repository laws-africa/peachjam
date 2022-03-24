from rest_framework import serializers
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from peachjam_search.documents import DecisionDocument

class DecisionSerializer(DocumentSerializer):

    class Meta:
        document = DecisionDocument
        fields = [
          'id', 
          'title', 
          'date',
          'author',
          'country',
          'citation',
          'matter_type',
          'document_content', 
          'source_url',
      ] 
