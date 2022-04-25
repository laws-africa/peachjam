from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from africanlii.models import Judgment, GenericDocument, LegalInstrument, Legislation
from peachjam.models import CoreDocument


@registry.register_document
class SearchableDocument(Document):
    doc_type = fields.KeywordField()
    title = fields.TextField()
    date = fields.DateField()
    year = fields.KeywordField(attr='date.year')
    citation = fields.TextField()
    content_html = fields.TextField()
    language = fields.KeywordField(attr="language.name_native")
    jurisdiction = fields.KeywordField(attr="jurisdiction.name")
    locality = fields.KeywordField(attr="locality.name")
    expression_frbr_uri = fields.KeywordField()
    work_frbr_uri = fields.KeywordField()
    created_at = fields.DateField()
    updated_at = fields.DateField()
    
    # Judgment
    matter_type = fields.KeywordField(attr="judgment.matter_type.name")
    case_number_string = fields.KeywordField(attr="judgment.case_number_string")
    court = fields.KeywordField(attr="judgment.court.name")
    headnote_holding = fields.TextField(attr="judgment.headnote_holding")
    flynote = fields.TextField(attr="judgment.flynote")
    judges = fields.TextField()

    # GenericDocument, LegalInstrument
    authoring_body = fields.KeywordField()
    nature = fields.KeywordField()

    class Index:
        name = "africanlii_documents"

    class Django:
        model = CoreDocument
        # to ensure the CoreDocument will be re-saved when Judgment, Legislation etc is updated
        related_models = [GenericDocument, Judgment, LegalInstrument, Legislation]

    def get_queryset(self):
        return super().get_queryset().select_related(
            'judgment', 'legalinstrument', 'legislation', 'genericdocument'
        )

    def get_instances_from_related(self, related_instance):
        """ Retrieve the CoreDocument instance from the related instance to ensure it is re-indexed
        when the related instance is updated.
        """
        if isinstance(related_instance, (GenericDocument, Judgment, LegalInstrument, Legislation)):
            return related_instance.coredocument_ptr

    def prepare_doc_type(self, instance):
        return instance.get_doc_type_display()

    def prepare_authoring_body(self, instance):
        if instance.doc_type == 'generic_document':
            return instance.genericdocument.authoring_body.name
        elif instance.doc_type == 'legal_instrument':
            return instance.legalinstrument.authoring_body.name

    def prepare_nature(self, instance):
        if instance.doc_type == 'generic_document':
            return instance.genericdocument.nature.name
        elif instance.doc_type == 'legal_instrument':
            return instance.legalinstrument.nature.name

    def prepare_judges(self, instance):
        if instance.doc_type == 'judgment':
            return [j.name for j in instance.judgment.judges.all()]

