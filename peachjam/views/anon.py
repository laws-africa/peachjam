import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.generic.detail import DetailView
from rest_framework import generics, serializers
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from peachjam.extractor import ExtractorError
from peachjam.models import Judgment, Replacement


class ReplacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Replacement
        fields = ["old_text", "new_text", "target"]


class DocumentAnonymiseSerializer(serializers.ModelSerializer):
    replacements = ReplacementSerializer(many=True)

    class Meta:
        model = Judgment
        fields = ["case_name", "content_html", "replacements", "published"]

    def update(self, instance, validated_data):
        replacements_data = validated_data.pop("replacements")

        super().update(instance, validated_data)

        # replace existing replacements
        instance.replacements.all().delete()
        for replacement_data in replacements_data:
            Replacement.objects.create(document=instance, **replacement_data)

        return instance


class DocumentAnonymiseView(PermissionRequiredMixin, DetailView):
    permission_required = "peachjam.change_judgment"
    template_name = "peachjam/anon/anonymise.html"
    model = Judgment
    context_object_name = "document"

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        if not document.content_html or document.content_html_is_akn:
            # redirect back to the referrer
            messages.warning(
                request, _("Only judgments with HTML content can be anonymised.")
            )
            return redirect(request.META.get("HTTP_REFERER", "/"))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["replacements"] = ReplacementSerializer(
            self.object.replacements.all(), many=True
        ).data

        return context


class DocumentAnonymiseAPIView(generics.UpdateAPIView):
    queryset = Judgment.objects.all()
    serializer_class = DocumentAnonymiseSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    def get_object(self):
        return generics.get_object_or_404(Judgment, pk=self.kwargs["pk"])


class SuggestPermissions(DjangoModelPermissions):
    perms_map = {
        "GET": ["%(app_label)s.change_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.change_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


class DocumentAnonymiseSuggestionsAPIView(generics.GenericAPIView):
    queryset = Judgment.objects.all()
    permission_classes = [IsAuthenticated, SuggestPermissions]
    api_token = settings.PEACHJAM["LAWSAFRICA_API_KEY"]
    api_url = settings.PEACHJAM["EXTRACTOR_API"]

    def get_object(self):
        return generics.get_object_or_404(Judgment, pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        document = self.get_object()
        suggestions = self.get_suggestions(
            document.get_content_as_text(), document.jurisdiction.pk
        )
        return Response({"suggestions": suggestions})

    def get_suggestions(self, text, country):
        text = text.strip()
        if not text or not self.api_token or not self.api_url:
            return []

        data = {
            "text": text,
            "country": country,
        }
        resp = requests.post(
            self.api_url + "anonymise/suggest",
            data=data,
            headers={"Authorization": "Token " + self.api_token},
        )
        if resp.status_code != 200:
            raise ExtractorError(
                f"Error calling extractor service: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        return data["anonymise"]["replacements"]
