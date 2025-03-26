from django.db.models import signals
from django.dispatch.dispatcher import receiver

from peachjam.models import DocumentContent
from peachjam_ml.tasks import update_document_embeddings


@receiver(signals.post_save)
def document_content_saved(sender, instance, **kwargs):
    """Update document chunks and embeddings when the content changes."""
    if isinstance(instance, DocumentContent) and not kwargs["raw"]:
        update_document_embeddings(instance.document_id, schedule=5)
