from rest_framework import generics

from .models import CitationLink
from .serializers import CitationLinkSerializer


class CitationLinkList(generics.ListCreateAPIView):
    queryset = CitationLink.objects.all()
    serializer_class = CitationLinkSerializer


class CitationLinkDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = CitationLink.objects.all()
    serializer_class = CitationLinkSerializer
