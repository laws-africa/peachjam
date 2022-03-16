from django_elasticsearch_dsl import Document
from django_elasticsearch_dsl.registries import registry
from peach_jam.models import Decision as DecisionModel

@registry.register_document
class DecisionDocument(Document):
    class Index:
      name = 'decisions'

    class Django:
      model = DecisionModel
      fields = [
          'id', 
          'title', 
          'date', 
          'citation', 
          'case_number_numeric', 
          'case_number_year', 
          'case_number_string', 
          'document_content', 
          'source_url', 
          'created_at', 
          'updated_at'
      ]
