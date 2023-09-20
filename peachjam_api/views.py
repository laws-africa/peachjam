from django import forms
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam.models import CaseNumber, CitationLink, Judgment, Relationship, Work
from peachjam.tasks import delete_document, update_document
from peachjam_api.permissions import CoreDocumentPermission
from peachjam_api.serializers import (
    CitationLinkSerializer,
    IngestorWebHookSerializer,
    RelationshipSerializer,
    WorkSerializer,
)


class RelationshipViewSet(viewsets.ModelViewSet):
    queryset = Relationship.objects.all()
    serializer_class = RelationshipSerializer


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
    authentication_classes = [authentication.TokenAuthentication]
    permission_classes = [CoreDocumentPermission]
    serializer_class = IngestorWebHookSerializer

    def post(self, request, ingestor_id):
        body = self.request.data

        serializer = self.serializer_class(data=body)
        if serializer.is_valid():
            if serializer.data["action"] == "updated":
                update_document(ingestor_id, serializer.data["data"]["url"])

            elif serializer.data["action"] == "deleted":
                delete_document(
                    ingestor_id, serializer.data["data"]["expression_frbr_uri"]
                )

            return Response({"data": serializer.data, "ingestor_id": ingestor_id})
        return Response(serializer.errors, status=400)


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


class DocumentProblemView(APIView):
    permission_classes = []

    def post(self, request):
        document_link = request.POST.get("document_link")
        problem_description = request.POST.get("problem_description")
        email_address = request.POST.get("email_address")

        message = render_to_string(
            "peachjam/document_problem_email.html",
            {
                "document_link": document_link,
                "problem_description": problem_description,
            },
        )

        recipient_list = [settings.DEFAULT_FROM_EMAIL]
        if email_address:
            recipient_list.append(email_address)

        send_mail(
            subject="Reported Document Problem",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=message,
        )

        return redirect(document_link)
