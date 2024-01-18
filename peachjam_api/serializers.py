from rest_framework import serializers
from rest_framework.reverse import reverse

from peachjam.models import (
    CitationLink,
    CoreDocument,
    Court,
    DocumentMedia,
    Gazette,
    Judgment,
    Label,
    Legislation,
    Predicate,
    Relationship,
    Work,
)


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
        fields = ("id", "document", "text", "url", "target_id", "target_selectors")


class ChildLegislationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Legislation
        fields = ("title", "citation", "work_frbr_uri", "repealed", "date")


class LegislationSerializer(serializers.ModelSerializer):
    taxonomies = serializers.SerializerMethodField("get_taxonomies")
    year = serializers.SerializerMethodField("get_year")
    children = ChildLegislationSerializer(many=True, read_only=True)
    languages = serializers.SerializerMethodField("get_languages")

    class Meta:
        model = Legislation
        fields = (
            "title",
            "children",
            "citation",
            "date",
            "work_frbr_uri",
            "repealed",
            "year",
            "taxonomies",
            "languages",
        )

    def get_taxonomies(self, instance):
        return [x.topic.name for x in instance.taxonomies.all()]

    def get_languages(self, instance):
        return instance.work.languages

    def get_year(self, instance):
        """Use the FRBR work uri, rather than the document year."""
        return instance.frbr_uri_date.split("-")[0]


class WebhookDataSerializer(serializers.Serializer):
    url = serializers.CharField()
    expression_frbr_uri = serializers.CharField()

    class Meta:
        fields = (
            "url",
            "expression_frbr_uri",
        )


class IngestorWebHookSerializer(serializers.Serializer):
    action = serializers.CharField()
    data = WebhookDataSerializer()

    class Meta:
        fields = (
            "action",
            "data",
        )


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        exclude = []


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ["id", "name", "code"]


class BaseSerializerMixin:
    def get_url(self, instance):
        # TODO: check https
        return self.context["request"].build_absolute_uri(instance.get_absolute_url())


class JudgmentSerializer(BaseSerializerMixin, serializers.ModelSerializer):
    court = CourtSerializer(read_only=True)
    url = serializers.SerializerMethodField()
    judges = serializers.SerializerMethodField()
    case_numbers = serializers.SerializerMethodField()

    class Meta:
        model = Judgment
        fields = (
            "case_numbers",
            "citation",
            "court",
            "created_at",
            "date",
            "expression_frbr_uri",
            "judges",
            "jurisdiction",
            "language",
            "locality",
            "mnc",
            "id",
            "title",
            "updated_at",
            "url",
            "work_frbr_uri",
        )

    def get_judges(self, instance):
        return [j.name for j in instance.judges.all()]

    def get_case_numbers(self, instance):
        return [str(c) for c in instance.case_numbers.all()]


class GazetteSerializer(BaseSerializerMixin, serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Gazette
        fields = (
            "created_at",
            "date",
            "expression_frbr_uri",
            "jurisdiction",
            "language",
            "locality",
            "id",
            "title",
            "updated_at",
            "url",
            "work_frbr_uri",
        )


class DocumentMediaSerializer(serializers.ModelSerializer):
    filename = serializers.CharField(max_length=1024, required=True)
    file = serializers.FileField(required=True, write_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentMedia
        fields = ("id", "filename", "file", "url")
        read_only_fields = ("mimetype",)

    def get_url(self, instance):
        if not instance.pk:
            return None
        return reverse(
            "document-attachments-detail",
            request=self.context["request"],
            kwargs={"pk": instance.pk},
        )
