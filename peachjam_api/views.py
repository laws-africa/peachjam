from rest_framework import authentication, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from peachjam.models import CitationLink, Relationship, Work
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
