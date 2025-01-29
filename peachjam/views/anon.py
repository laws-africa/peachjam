from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic.detail import DetailView
from rest_framework import generics, serializers
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated

from peachjam.models import Judgment, Replacement


class ReplacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Replacement
        fields = ["old_text", "new_text", "target"]


class DocumentUpdateSerializer(serializers.ModelSerializer):
    replacements = ReplacementSerializer(many=True)

    class Meta:
        model = Judgment
        fields = ["content_html", "replacements"]

    def update(self, instance, validated_data):
        replacements_data = validated_data.pop("replacements")
        instance.content_html = validated_data.get(
            "content_html", instance.content_html
        )
        instance.save()

        # Clear existing replacements
        instance.replacements.all().delete()

        # Create new replacements
        for replacement_data in replacements_data:
            Replacement.objects.create(document=instance, **replacement_data)

        return instance


class DocumentAnonymiseView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam.change_judgment"
    template_name = "peachjam/anon/anonymise.html"
    model = Judgment
    context_object_name = "document"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["replacements"] = ReplacementSerializer(
            self.object.replacements.all(), many=True
        ).data

        return context


class DocumentAnonymiseAPIView(generics.UpdateAPIView):
    queryset = Judgment.objects.all()
    serializer_class = DocumentUpdateSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    def get_object(self):
        return generics.get_object_or_404(Judgment, pk=self.kwargs["pk"])
