from rest_framework import serializers

from peachjam.models import CoreDocument

from .models import CitationLink


class CoreDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoreDocument
        fields = "__all__"


class CitationLinkSerializer(serializers.ModelSerializer):
    document = CoreDocumentSerializer(read_only=True)

    class Meta:
        model = CitationLink
        fields = ("document", "text", "url", "target_id", "target_selectors")
