from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
# from django_elasticsearch_dsl_drf.serializers import DocumentSerialzier
from peach_jam.models import Decision as DecisionModel

@registry.register_document
class DecisionDocument(Document):

    title = fields.TextField()
    citation = fields.TextField()
    document_content = fields.TextField()
    author = fields.TextField(attr='author.name')
    country = fields.KeywordField(attr='author.country.name')
    matter_type = fields.TextField(attr='matter_type.name')
    year = fields.IntegerField(attr='case_number_year')
    case_number = fields.IntegerField(attr='case_number_numeric')
    source_url = fields.TextField()
    date = fields.DateField()
    class Index:
      name = 'decisions'

    class Django:
      model = DecisionModel
   
