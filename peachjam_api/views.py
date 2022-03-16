from rest_framework import viewsets
from rest_framework import permissions

from peach_jam.models import Decision
from peachjam_api.serializers import DecisionSerializer



class DecisionViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows decisions to be viewed or edited.
    """
    queryset = Decision.objects.all().order_by('-date')
    serializer_class = DecisionSerializer
    permission_classes = [permissions.IsAuthenticated]
