from rest_framework import serializers
from peach_jam.models import Decision

class DecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = ['title', 'author', 'citation']
