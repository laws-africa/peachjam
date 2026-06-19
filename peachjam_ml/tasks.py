import logging

from background_task import background
from django.db import transaction

from peachjam.logging import log_context
from peachjam.models import CoreDocument
from peachjam_ml.models import DocumentEmbedding

log = logging.getLogger(__name__)


@background(queue="peachjam", remove_existing_tasks=True)
@transaction.atomic
def update_document_embeddings(document_id):
    log.info(f"Updating document embeddings for document {document_id}")

    document = CoreDocument.objects.filter(pk=document_id).first()
    if not document:
        log.info(f"No document with id {document_id} exists, ignoring.")
        return

    with log_context(frbr_uri=document.expression_frbr_uri):
        DocumentEmbedding.refresh_for_document_content(document)
        log.info("Done")


@background(queue="peachjam", remove_existing_tasks=True)
@transaction.atomic
def update_summary_embeddings(document_id):
    log.info(f"Updating summary embeddings for document {document_id}")

    document = CoreDocument.objects.filter(pk=document_id).first()
    if not document:
        log.info(f"No document with id {document_id} exists, ignoring.")
        return

    with log_context(frbr_uri=document.expression_frbr_uri):
        DocumentEmbedding.refresh_for_document_summary(document)
        log.info("Done")
