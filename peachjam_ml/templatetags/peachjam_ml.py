from django import template
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from peachjam_ml.models import ChatThread

register = template.Library()


@register.simple_tag
def recent_chats(user):
    """Return the 10 most recent chat threads, one per document, for the supplied user."""
    if not user or not getattr(user, "is_authenticated", False):
        return ChatThread.objects.none()

    return (
        ChatThread.objects.filter(user=user)
        .annotate(
            document_rank=Window(
                expression=RowNumber(),
                partition_by=[F("document_id")],
                order_by=F("updated_at").desc(),
            )
        )
        .filter(document_rank=1)
        .select_related("document")
        .order_by("-updated_at")[:10]
    )
