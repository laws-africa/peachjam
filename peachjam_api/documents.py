from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
# from django_elasticsearch_dsl_drf.serializers import DocumentSerialzier
from peach_jam.models import Decision as DecisionModel

@registry.register_document
class DecisionDocument(Document):

    title = fields.TextField()
    date = fields.DateField()
    citation = fields.TextField()
    document_content = fields.TextField()
    author = fields.KeywordField(attr='author.name')
    country = fields.KeywordField(attr='author.country.name')
    matter_type = fields.KeywordField(attr='matter_type.name')
    created_at = fields.DateField()
    updated_at = fields.DateField()
    class Index:
      name = 'decisions'

    class Django:
      model = DecisionModel
   
