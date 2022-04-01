from django_elasticsearch_dsl import Document
from django_elasticsearch_dsl import fields
from django_elasticsearch_dsl.registries import registry

from africanlii.models import Judgment


@registry.register_document
class JudgmentDocument(Document):
    title = fields.TextField()
    date = fields.DateField()
    citation = fields.TextField()
    document_content = fields.TextField()
    author = fields.KeywordField(attr="author.name")
    country = fields.KeywordField(attr="author.country.name")
    matter_type = fields.KeywordField(attr="matter_type.name")
    created_at = fields.DateField()
    updated_at = fields.DateField()

    class Index:
        name = "africanlii_judgments"

    class Django:
        model = Judgment
