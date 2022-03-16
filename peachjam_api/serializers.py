from rest_framework import serializers
from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from peachjam_api.documents import DecisionDocument

class DecisionSerializer(DocumentSerializer):

    class Meta:
        document = DecisionDocument
        fields = [
          'id', 
          'title', 
          'author',
          'country',
          'citation', 
          'matter_type',
          'case_number_numeric', 
          'case_number_year', 
          'case_number_string', 
          'document_content', 
          'source_url',
      ] 
