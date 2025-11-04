from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    id = serializers.CharField(required=True)
