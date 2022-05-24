from rest_framework import viewsets

from peachjam.models import Relationship
from peachjam_api.serializers import RelationshipSerializer


class RelationshipViewSet(viewsets.ModelViewSet):
    queryset = Relationship.objects.all()
    serializer_class = RelationshipSerializer
