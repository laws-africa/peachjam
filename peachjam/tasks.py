import logging

from background_task import background
from background_task.tasks import DBTaskRunner, Task, logger, tasks
from django.db.utils import OperationalError

log = logging.getLogger(__name__)


class PatchedDBTaskRunner(DBTaskRunner):
    """Patch DBTaskRunner to be more efficient when pulling tasks from the database. This can be dropped once
    https://github.com/arteria/django-background-tasks/pull/244/files is merged into django-background-task.
    """

    def get_task_to_run(self, tasks, queue=None):
        try:
            # This is the changed line
            available_tasks = Task.objects.find_available(queue).filter(
                task_name__in=tasks._tasks
            )[:5]
            for task in available_tasks:
                # try to lock task
                locked_task = task.lock(self.worker_name)
                if locked_task:
                    return locked_task
            return None
        except OperationalError:
            logger.warning("Failed to retrieve tasks. Database unreachable.")


# use the patched runner
tasks._runner = PatchedDBTaskRunner()


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
