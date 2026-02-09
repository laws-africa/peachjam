from asgiref.sync import async_to_sync
from django.db.models import signals
from django.dispatch.dispatcher import receiver

from peachjam.models import DocumentContent, Judgment
from peachjam.models.lifecycle import after_attribute_changed
from peachjam_ml.chat.agent import get_session
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
    """Cleanup chat session data."""
    session = get_session(instance)
    async_to_sync(session.clear_session)()
