from rest_framework import serializers

from peachjam.models import CoreDocument, Predicate, Relationship


class PredicateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Predicate
        exclude = []


class RelationshipDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoreDocument
        fields = ["expression_frbr_uri", "date", "language"]


class RelationshipSerializer(serializers.ModelSerializer):
    predicate = PredicateSerializer()
    object_documents = RelationshipDocumentSerializer(many=True, read_only=True)
    subject_documents = RelationshipDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Relationship
        fields = [
            "id",
            "subject_work_frbr_uri",
            "subject_target_id",
            "object_work_frbr_uri",
            "object_target_id",
            "predicate",
            "subject_documents",
            "object_documents",
        ]
