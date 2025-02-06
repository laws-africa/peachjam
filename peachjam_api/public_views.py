from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    BasePermission,
    DjangoModelPermissions,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam.models import Gazette, Judgment, Ratification
from peachjam_api.serializers import (
    BatchValidateFrbrUrisRequestSerializer,
    BatchValidateFrbrUrisResponseSerializer,
    GazetteSerializer,
    JudgmentSerializer,
    RatificationSerializer,
)


class JudgmentAPIPermission(BasePermission):
    permission_name = "peachjam.api_judgment"

    def has_permission(self, request, view):
        # user must have perms to access judgments through the api
        return (
            request.user
            and request.user.is_authenticated
            and request.user.has_perm(self.permission_name)
        )


class GazetteAPIPermission(JudgmentAPIPermission):
    permission_name = "peachjam.api_gazette"


class RatificationAPIPermission(JudgmentAPIPermission):
    permission_name = "peachjam.api_ratification"


class BaseDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "expression_frbr_uri"
    permission_classes = [DjangoModelPermissions]
    filterset_fields = {
        "jurisdiction": ["exact"],
        "work_frbr_uri": ["exact"],
        "title": ["exact", "icontains"],
        "date": ["exact", "gte", "lte"],
        "updated_at": ["exact", "gte", "lte"],
        "created_at": ["exact", "gte", "lte"],
    }
    ordering_fields = ["title", "date", "updated_at", "created_at"]
    ordering = ["updated_at"]

    @extend_schema(responses={(200, "text/plain"): OpenApiTypes.STR})
    @action(detail=True, url_path="source.txt")
    def source_txt(self, request, expression_frbr_uri=None):
        """Source document in text form (if available)."""
        obj = self.get_object()
        # we only allow certain formats
        try:
            content = getattr(obj, "document_content")
        except AttributeError:
            raise Http404()

        # return content.content_text as a normal drf response object
        return HttpResponse(content.content_text, content_type="text/plain")

    @extend_schema(responses={(200, "text/html"): OpenApiTypes.STR})
    @action(detail=True, url_path=".html")
    def content_html(self, request, expression_frbr_uri=None):
        obj = self.get_object()
        content = obj.content_html
        if not content:
            raise Http404()
        return HttpResponse(content, content_type="text/html")

    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    @action(detail=True, url_path="source.pdf")
    def source_pdf(self, request, expression_frbr_uri=None):
        """Source document in PDF form (if available)."""
        obj = self.get_object()
        # we only allow certain formats
        try:
            source_file = getattr(obj, "source_file")
        except AttributeError:
            raise Http404()

        if not source_file.file or source_file.mimetype != "application/pdf":
            raise Http404()

        return self.make_response(
            source_file.file, source_file.mimetype, source_file.filename_for_download()
        )

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, url_path="source.file")
    def source_file(self, request, expression_frbr_uri=None):
        obj = self.get_object()
        try:
            source_file = getattr(obj, "source_file")
        except AttributeError:
            raise Http404()

        if not source_file.file:
            raise Http404()

        return self.make_response(
            source_file.file, source_file.mimetype, source_file.filename_for_download()
        )

    def make_response(self, f, content_type, fname):
        file_bytes = f.read()
        response = HttpResponse(file_bytes, content_type=content_type)
        response["Content-Disposition"] = f"inline; filename={fname}"
        response["Content-Length"] = str(len(file_bytes))
        return response


class GazettesViewSet(BaseDocumentViewSet):
    permission_classes = [
        GazetteAPIPermission,
        DjangoModelPermissions,
    ]
    queryset = Gazette.objects.all()
    serializer_class = GazetteSerializer


class JudgmentsViewSet(BaseDocumentViewSet):
    permission_classes = [
        JudgmentAPIPermission,
        DjangoModelPermissions,
    ]
    queryset = (
        Judgment.objects.select_related("court", "registry", "locality")
        .prefetch_related("judges", "case_numbers", "taxonomies")
        .all()
    )
    serializer_class = JudgmentSerializer
    filterset_fields = BaseDocumentViewSet.filterset_fields.copy()
    filterset_fields.update(
        {
            "court__code": ["exact"],
            "registry__code": ["exact"],
        }
    )


class RatificationsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [
        RatificationAPIPermission,
        DjangoModelPermissions,
    ]
    queryset = (
        Ratification.objects.select_related("work").prefetch_related("countries").all()
    )
    serializer_class = RatificationSerializer
    filterset_fields = {
        "updated_at": ["exact", "gte", "lte"],
    }
    ordering = ["updated_at"]


class ValidateExpressionFrbrUrisView(APIView):
    """Validates a list of decision expression FRBR URIs and returns those that aren't valid."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = BatchValidateFrbrUrisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        frbr_uris = serializer.validated_data["expression_frbr_uris"]

        # Check which URIs are not valid in bulk
        invalid_uris = self.get_invalid_uris(frbr_uris)

        response_serializer = BatchValidateFrbrUrisResponseSerializer(
            data={"invalid_expression_frbr_uris": list(invalid_uris)}
        )
        response_serializer.is_valid(raise_exception=True)

        # Return the invalid URIs
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def get_invalid_uris(self, frbr_uris):
        valid_uris = Judgment.objects.filter(
            expression_frbr_uri__in=frbr_uris
        ).values_list("expression_frbr_uri", flat=True)
        return set(frbr_uris) - set(valid_uris)
