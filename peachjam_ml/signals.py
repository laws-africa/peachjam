from django.db.models import signals
from django.dispatch.dispatcher import receiver

from peachjam.models import DocumentContent, Judgment
from peachjam.models.lifecycle import after_attribute_changed
from peachjam_ml.chat.graphs import get_graph_memory
from peachjam_ml.models import ChatThread
from peachjam_ml.tasks import update_document_embeddings, update_summary_embeddings


@receiver(signals.post_save, sender=DocumentContent)
def document_content_saved(sender, instance, **kwargs):
    """Update document chunks and embeddings when the content changes."""
    if not kwargs["raw"]:
        update_document_embeddings(instance.document_id, schedule=5)


@after_attribute_changed(
    Judgment, ["blurb", "case_summary", "flynote", "held", "issues", "order"]
)
def when_case_summary_changed(judgment):
    update_summary_embeddings(judgment.id, schedule=5)


@receiver(signals.post_delete, sender=ChatThread)
def chat_thread_deleted(sender, instance, **kwargs):
    """Cleanup langgraph checkpoint data."""
    with get_graph_memory() as memory:
        memory.delete_thread(str(instance.id))
