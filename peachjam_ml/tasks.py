import logging

from background_task import background

from peachjam.models import CoreDocument
from peachjam_ml.models import DocumentEmbedding

log = logging.getLogger(__name__)


@background(queue="peachjam", remove_existing_tasks=True)
def update_document_embeddings(document_id):
    log.info(f"Updating document embeddings for document {document_id}")

    document = CoreDocument.objects.filter(pk=document_id).first()
    if not document:
        log.info(f"No document with id {document_id} exists, ignoring.")
        return

    DocumentEmbedding.refresh_for_document(document)
    log.info("Done")
