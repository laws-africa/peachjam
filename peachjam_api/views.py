from rest_framework import generics, viewsets

from peachjam.models import CitationLink, Relationship, Work
from peachjam_api.serializers import (
    CitationLinkSerializer,
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


class CitationLinkList(generics.ListCreateAPIView):
    queryset = CitationLink.objects.all()
    serializer_class = CitationLinkSerializer


class CitationLinkDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = CitationLink.objects.all()
    serializer_class = CitationLinkSerializer
