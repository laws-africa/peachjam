from rest_framework import serializers

from peachjam.models import CitationLink, CoreDocument, Predicate, Relationship, Work


class WorkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Work
        exclude = []


class PredicateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Predicate
        exclude = []


class RelationshipDocumentSerializer(serializers.ModelSerializer):
    language3 = serializers.CharField(read_only=True, source="language.iso_639_3")

    class Meta:
        model = CoreDocument
        fields = ["title", "expression_frbr_uri", "date", "language", "language3"]


class RelationshipSerializer(serializers.ModelSerializer):
    subject_work = WorkSerializer(read_only=True)
    subject_work_id = serializers.PrimaryKeyRelatedField(
        write_only=True, source="subject_work", queryset=Work.objects.all()
    )
    object_work = WorkSerializer(read_only=True)
    object_work_id = serializers.PrimaryKeyRelatedField(
        write_only=True, source="object_work", queryset=Work.objects.all()
    )
    predicate = PredicateSerializer(read_only=True)
    predicate_id = serializers.PrimaryKeyRelatedField(
        write_only=True, source="predicate", queryset=Predicate.objects.all()
    )
    object_documents = RelationshipDocumentSerializer(many=True, read_only=True)
    subject_documents = RelationshipDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Relationship
        fields = [
            "id",
            "subject_work",
            "subject_work_id",
            "subject_target_id",
            "object_work",
            "object_work_id",
            "object_target_id",
            "predicate",
            "predicate_id",
            "subject_documents",
            "object_documents",
        ]


class CitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitationLink
        fields = ("document", "text", "url", "target_id", "target_selectors")
