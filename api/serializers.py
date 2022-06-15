from rest_framework import serializers

from .models import CitationLink


class CitationLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitationLink
        fields = ("document", "text", "url", "target_id", "target_selectors")
