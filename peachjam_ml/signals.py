from django.db.models import signals
from django.dispatch.dispatcher import receiver
from django_lifecycle import AFTER_SAVE

from peachjam.models import DocumentContent, Judgment
from peachjam.models.lifecycle import on_attribute_changed
from peachjam_ml.tasks import update_document_embeddings, update_summary_embeddings


@receiver(signals.post_save, sender=DocumentContent)
def document_content_saved(sender, instance, **kwargs):
    """Update document chunks and embeddings when the content changes."""
    if not kwargs["raw"]:
        update_document_embeddings(instance.document_id, schedule=5)


@on_attribute_changed(
    Judgment,
    AFTER_SAVE,
    ["blurb", "case_summary", "flynote", "held", "issues", "order"],
    ["Judgment.summary_embeddings"],
)
def when_case_summary_changed(judgment):
    update_summary_embeddings(judgment.id, schedule=5)
