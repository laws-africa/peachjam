import logging

from background_task import background

log = logging.getLogger(__name__)


@background(remove_existing_tasks=True)
def update_document(ingestor_id, document_id):
    from peachjam.models import Ingestor

    log.info(f"Updating document {document_id} with ingestor {ingestor_id}")

    ingestor = Ingestor.objects.fillter(pk=ingestor_id).first()
    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} exists, igoring.")
        return
    ingestor.update_document(document_id)
    log.info("Done")


@background(remove_existing_tasks=True)
def run_ingestors():
    from peachjam.models import Ingestor

    log.info("Running ingestors...")

    for ingestor in Ingestor.objects.all():
        ingestor.check_for_updates()

    log.info("Done")
