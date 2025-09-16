from django import forms
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views import View
from rest_framework import viewsets
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam.auth import user_display
from peachjam.models import (
    Annotation,
    CaseNumber,
    CitationLink,
    Ingestor,
    Judgment,
    Relationship,
    Work,
)
from peachjam_api.serializers import (
    AnnotationSerializer,
    CitationLinkSerializer,
    RelationshipSerializer,
    WorkSerializer,
)


class RelationshipViewSet(viewsets.ModelViewSet):
    queryset = Relationship.objects.all()
    serializer_class = RelationshipSerializer


class AnnotationViewSet(viewsets.ModelViewSet):
    queryset = Annotation.objects.all()
    serializer_class = AnnotationSerializer
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self, *args, **kwargs):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
            document_id = self.kwargs.get("document_id")
            if document_id:
                queryset = queryset.filter(document__id=document_id)
            return queryset
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WorksViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Work.objects.all()
    serializer_class = WorkSerializer
    filterset_fields = {
        "frbr_uri": ["exact"],
        "title": ["exact", "icontains"],
    }


class CitationLinkViewSet(viewsets.ModelViewSet):
    queryset = CitationLink.objects.all()
    serializer_class = CitationLinkSerializer


class IngestorWebhookView(APIView):
    permission_classes = []

    def post(self, request, ingestor_id):
        ingestor = get_object_or_404(Ingestor, pk=ingestor_id)
        if ingestor.enabled:
            # read the request body; this allows the ingestor and the adapter to inspect request.body later on
            body = request.body  # noqa
            ingestor.handle_webhook(request, request.data)
        return Response({}, status=200)


class DuplicateForm(forms.Form):
    court = forms.CharField(max_length=100)
    date = forms.DateField()


class CaseNumberForm(forms.ModelForm):
    class Meta:
        model = CaseNumber
        fields = [
            "string_override",
            "string",
            "number",
            "year",
            "matter_type",
        ]
        exclude = ["document", "id"]


class CheckDuplicatesView(APIView):
    permission_classes = []

    def post(self, request):
        judgment_id = request.POST.get("judgment_id")
        duplicate_form = DuplicateForm(request.POST)
        CaseNumberFormSet = forms.modelformset_factory(
            CaseNumber,
            form=CaseNumberForm,
            min_num=1,
            validate_min=True,
        )
        case_number_formset = CaseNumberFormSet(
            prefix="case_numbers", data=request.POST
        )

        if duplicate_form.is_valid() and case_number_formset.is_valid():
            # get form data and build query
            q = Q()
            for case_number in case_number_formset.cleaned_data:
                # new query for each case number
                case_query = {}
                for field, value in case_number.items():
                    if field == "id":
                        continue
                    if value:
                        case_query[f"case_numbers__{field}"] = value
                q |= Q(**case_query)

            q &= Q(
                court=duplicate_form.cleaned_data["court"],
                date=duplicate_form.cleaned_data["date"],
            )

            # check for potential duplicates
            qs = Judgment.objects.filter(q)
            if judgment_id:
                qs = qs.exclude(id=judgment_id)
            duplicate = qs.first()

            if duplicate:
                url = reverse("admin:peachjam_judgment_change", args=[duplicate.pk])
                html = format_html(
                    "<div id='duplicate-alert' class='alert alert-danger' role='alert'>"
                    f"{_('Possible duplicate of')} "
                    f"<a target='_blank' href='{url}'>{duplicate}</a>"
                    "</div>",
                )
                return Response(html)
        return Response()


class GetAccountView(View):
    def get_object(self):
        return self.request.user

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            user_details = {
                "id": self.request.user.id,
                "email": self.request.user.email,
                "name": user_display(self.request.user),
            }
            response = JsonResponse(user_details)
            return response
        return HttpResponse(status=404)
