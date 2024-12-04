from rest_framework import serializers

from peachjam.models import (
    CaseNumber,
    CitationLink,
    CoreDocument,
    Court,
    Gazette,
    Judgment,
    Label,
    Legislation,
    Locality,
    Predicate,
    Ratification,
    RatificationCountry,
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
            "subject_selectors",
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


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ("name", "level")


class ChildLegislationSerializer(serializers.ModelSerializer):
    year = serializers.SerializerMethodField("get_year")
    labels = LabelSerializer(many=True, read_only=True)

    class Meta:
        model = Legislation
        fields = ("title", "citation", "work_frbr_uri", "repealed", "year", "labels")

    def get_year(self, instance):
        """Use the FRBR work uri, rather than the document year."""
        return instance.frbr_uri_date.split("-")[0]


class LegislationSerializer(serializers.ModelSerializer):
    taxonomies = serializers.SerializerMethodField("get_taxonomies")
    year = serializers.SerializerMethodField("get_year")
    children = ChildLegislationSerializer(many=True, read_only=True)
    languages = serializers.SerializerMethodField("get_languages")
    labels = LabelSerializer(many=True, read_only=True)

    class Meta:
        model = Legislation
        fields = (
            "title",
            "children",
            "citation",
            "work_frbr_uri",
            "repealed",
            "year",
            "taxonomies",
            "languages",
            "labels",
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


class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        exclude = []


class CourtSerializer(serializers.ModelSerializer):
    class Meta:
        model = Court
        fields = ["id", "name", "code"]


class CaseNumbersSerializer(serializers.ModelSerializer):
    matter_type = serializers.CharField(source="matter_type.name", allow_null=True)

    class Meta:
        model = CaseNumber
        fields = ["string_override", "matter_type", "year", "string", "number"]


class LocalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Locality
        fields = ["name", "code"]


class BaseSerializerMixin:
    def get_url(self, instance):
        # TODO: check https
        return self.context["request"].build_absolute_uri(instance.get_absolute_url())


class JudgmentSerializer(BaseSerializerMixin, serializers.ModelSerializer):
    court = CourtSerializer(read_only=True)
    url = serializers.SerializerMethodField()
    judges = serializers.SerializerMethodField()
    case_numbers = CaseNumbersSerializer(many=True, read_only=True)
    locality = LocalitySerializer(read_only=True)
    topics = serializers.SerializerMethodField()

    class Meta:
        model = Judgment
        fields = (
            "case_numbers",
            "case_name",
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
            "topics",
        )

    def get_judges(self, instance):
        return [j.name for j in instance.judges.all()]

    def get_topics(self, instance):
        return [t.topic.name for t in instance.taxonomies.all()]


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


class RatificationCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RatificationCountry
        exclude = ["id", "ratification"]


class RatificationSerializer(serializers.ModelSerializer):
    countries = RatificationCountrySerializer(many=True)
    work = serializers.CharField(source="work.frbr_uri")

    class Meta:
        model = Ratification
        fields = (
            "work",
            "last_updated",
            "countries",
        )
