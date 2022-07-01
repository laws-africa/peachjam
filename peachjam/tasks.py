import logging

from background_task import background

log = logging.getLogger(__name__)


@background(remove_existing_tasks=True)
def update_document(ingestor_id, document_id):
    from peachjam.models import Ingestor

    log.info(f"Updating document {document_id} with ingestor {ingestor_id}")

    ingestor = Ingestor.objects.filter(pk=ingestor_id).first()
    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} exists, ignoring.")
        return

    try:
        ingestor.update_document(document_id)
    except Exception as e:
        log.error("Error updating document", exc_info=e)
        raise

    log.info("Update document done")


@background(remove_existing_tasks=True)
def run_ingestors():
    from peachjam.models import Ingestor

    log.info("Running ingestors...")

    for ingestor in Ingestor.objects.all():
        ingestor.check_for_updates()

    log.info("Running ingestors done")
