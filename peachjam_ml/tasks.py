import logging

from background_task import background
from django.db import transaction

from peachjam.models import CoreDocument, Judgment
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

    DocumentEmbedding.refresh_for_document_summary(document)
    log.info("Done")


@background(queue="peachjam", remove_existing_tasks=True)
@transaction.atomic
def update_flynote_taxonomy(document_id):
    """Use the LLM mapper to automatically map a judgment's flynote
    to taxonomy topics when the flynote is created or updated."""
    from peachjam.models.settings import pj_settings
    from peachjam.models.taxonomies import DocumentTopic
    from peachjam_ml.flynote_mapper import FlynoteLLMMapper

    log.info(f"Mapping flynote to taxonomy for judgment {document_id}")

    judgment = Judgment.objects.filter(pk=document_id).first()
    if not judgment or not judgment.flynote:
        log.info(f"No judgment or flynote for {document_id}, skipping.")
        return

    root = pj_settings().flynote_taxonomy_root
    if not root:
        log.info("No flynote_taxonomy_root configured, skipping.")
        return

    mapper = FlynoteLLMMapper()
    try:
        matches = mapper.map_flynote(judgment.flynote)
    except Exception:
        log.exception(f"Error mapping flynote for judgment {document_id}")
        return

    for topic in matches:
        DocumentTopic.objects.get_or_create(
            document_id=document_id,
            topic_id=topic["id"],
        )

    log.info(f"Mapped {len(matches)} topic(s) for judgment {document_id}")
