from rest_framework import viewsets

from peachjam.models import Judgment
from peachjam_api.serializers import JudgmentSerializer


class JudgmentsViewSet(viewsets.ReadOnlyModelViewSet):
    # TODO: auth, perms
    queryset = Judgment.objects.select_related("court").all()
    serializer_class = JudgmentSerializer
    filterset_fields = {
        "title": ["exact", "icontains"],
        "date": ["exact", "gte", "lte"],
        "updated_at": ["exact", "gte", "lte"],
        "created_at": ["exact", "gte", "lte"],
    }
    ordering_fields = ["title", "date", "updated_at", "created_at"]
    ordering = ["date"]
