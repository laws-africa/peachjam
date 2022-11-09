import logging

from background_task import background

log = logging.getLogger(__name__)


@background(queue="peachjam", remove_existing_tasks=True)
def update_document(ingestor_id, document_id):
    from peachjam.models import Ingestor

    ingestor = Ingestor.objects.filter(pk=ingestor_id).first()
    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} exists, ignoring.")
        return

    if ingestor.enabled:
        log.info(f"Updating document {document_id} with ingestor {ingestor}")
        try:
            ingestor.update_document(document_id)
        except Exception as e:
            log.error("Error updating document", exc_info=e)
            raise

        log.info("Update document done")
        return

    log.info("Ingestor is disabled, ignoring.")


@background(queue="peachjam", schedule=(60 * 5), remove_existing_tasks=True)
def delete_document(ingestor_id, expression_frbr_uri):
    from peachjam.models import Ingestor

    ingestor = Ingestor.objects.filter(pk=ingestor_id).first()

    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} ")
    if ingestor.enabled:
        log.info(f"Deleting document {expression_frbr_uri} with ingestor {ingestor}")

        try:
            ingestor.delete_document(expression_frbr_uri)
        except Exception as e:
            log.error("Error deleting document", exc_info=e)
            raise

        log.info("Document deleted")
        return

    log.info("Ingestor is disabled, ignoring.")


@background(queue="peachjam", remove_existing_tasks=True)
def run_ingestors():
    from peachjam.models import Ingestor

    log.info("Running ingestors...")

    for ingestor in Ingestor.objects.all():
        if ingestor.enabled:
            ingestor.check_for_updates()

    log.info("Running ingestors done")
