import logging

import sentry_sdk
from background_task import background
from background_task.signals import task_error
from background_task.tasks import DBTaskRunner, Task, logger, tasks
from django.db.utils import OperationalError
from django.dispatch import receiver
from sentry_sdk.tracing import TRANSACTION_SOURCE_TASK

from peachjam.models import CoreDocument, Work, citations_processor

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

    def run_task(self, tasks, task):
        # wrap the task in a sentry transaction
        with sentry_sdk.start_transaction(
            op="queue.task", source=TRANSACTION_SOURCE_TASK, name=task.task_name
        ) as transaction:
            transaction.set_status("ok")
            super().run_task(tasks, task)


# use the patched runner
tasks._runner = PatchedDBTaskRunner()


@receiver(task_error)
def on_task_error(*args, **kwargs):
    # report the exception to Sentry
    hub = sentry_sdk.Hub.current
    hub.capture_exception()

    # now mark the current transaction as handled, otherwise it'll be reported twice
    if hub.scope and hub.scope.transaction:
        hub.scope.transaction.timestamp = -1


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
        return
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
def run_ingestor(ingestor_id):
    """Run an ingestor."""
    from peachjam.models import Ingestor

    log.info(f"Running ingestor {ingestor_id}...")

    ingestor = Ingestor.objects.filter(pk=ingestor_id).first()
    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} exists, ignoring.")
        return

    if ingestor.enabled:
        ingestor.check_for_updates()
        log.info("Done")
    else:
        log.info("Ingestor not enabled, ignoring.")


# this can be slow and is not urgent, run at a lower priority
@background(queue="peachjam", remove_existing_tasks=True, schedule={"priority": -1})
def extract_citations(document_id):
    """Extract citations from a document in the background."""

    log.info(f"Extracting citations for document {document_id}")

    doc = CoreDocument.objects.filter(pk=document_id).first()
    if not doc:
        log.info(f"No document with id {document_id} exists, ignoring.")
        return

    try:
        if doc.extract_citations():
            doc.save()

        extract_citation_contexts(document_id)
    except Exception as e:
        log.error(f"Error extracting citations for {doc}", exc_info=e)
        raise

    log.info("Citations extracted")


@background(queue="peachjam", remove_existing_tasks=True, schedule={"priority": -2})
def extract_citation_contexts(document_id):
    """Extract citation contexts from a document in the background."""

    log.info(f"Extracting citation contexts for document {document_id}")

    doc = CoreDocument.objects.filter(pk=document_id).first()
    if not doc:
        log.info(f"No document with id {document_id} exists, ignoring.")
        return
    if not doc.is_latest_expression:
        log.info(
            f"Document is not latest_expression {document_id}, skipping context extraction."
        )
        return

    try:
        doc.extract_citation_contexts()
    except Exception as e:
        log.error(f"Error extracting citation contexts for {doc}", exc_info=e)
        raise

    log.info("Citation contexts extracted")


@background(queue="peachjam", schedule=60, remove_existing_tasks=True)
def update_extracted_citations_for_a_work(work_id):
    """Update Extracted Citations for a work."""

    work = Work.objects.filter(pk=work_id).first()
    if not work:
        log.info(f"No work with id {work_id} exists, ignoring.")
        return

    log.info(f"Updating extracted citations for work {work_id}")

    try:
        work.update_extracted_citations()
        log.info(f"Citations for work {work_id} updated")

    except Exception as e:
        log.error(f"Error updating citations for {work_id}", exc_info=e)
        raise e


@background(queue="peachjam", schedule=60 * 60, remove_existing_tasks=True)
def re_extract_citations():
    cp = citations_processor()
    cp.re_extract_citations()


@background(queue="peachjam", remove_existing_tasks=True)
def convert_source_file_to_pdf(source_file_id):
    from peachjam.models import SourceFile

    source_file = SourceFile.objects.filter(pk=source_file_id).first()
    if not source_file:
        log.info(f"No source file with id {source_file_id} exists, ignoring.")
        return

    log.info(f"Converting source file {source_file_id} to PDF")

    try:
        source_file.convert_to_pdf()

    except Exception as e:
        log.error(f"Error converting source file {source_file_id} to PDF", exc_info=e)
        raise e

    log.info("Conversion to PDF done")


@background(queue="peachjam", remove_existing_tasks=True)
def create_anonymised_source_file_pdf(doc_id):
    from peachjam.models import Judgment

    doc = Judgment.objects.filter(id=doc_id).first()
    logger.info(f"Creating anonymised source file PDF for judgment {doc_id}")
    if not doc:
        logger.warning("Judgment not found")
        return
    doc.create_anonymised_source_file_pdf()
    logger.info("Done")


@background(queue="peachjam", remove_existing_tasks=True)
def rank_works():
    from peachjam.analysis.ranker import GraphRanker

    GraphRanker().rank_and_publish()


@background(queue="peachjam", remove_existing_tasks=True)
def get_deleted_documents(ingestor_id, range_start, range_end):
    from peachjam.models import Ingestor

    ingestor = Ingestor.objects.get(pk=ingestor_id)
    if not ingestor.enabled:
        log.info(f"ingestor {ingestor.name} disabled, ignoring")
        return

    adapter = ingestor.get_adapter()
    adapter.get_deleted_documents(range_start, range_end)


@background(queue="peachjam", remove_existing_tasks=True)
def update_user_follows():
    from django.contrib.auth import get_user_model

    log.info("Updating user follows")
    users = get_user_model().objects.filter(following__isnull=False).distinct()
    for user in users:
        update_user_follows_for_user(user.pk)


@background(queue="peachjam", remove_existing_tasks=True)
def update_user_follows_for_user(user_id):
    from django.contrib.auth import get_user_model

    from peachjam.models import UserFollowing

    user = get_user_model().objects.filter(pk=user_id).first()
    if not user:
        log.info(f"No user with id {user_id} exists, ignoring.")
        return

    log.info(f"Updating user follows for user {user_id}")
    UserFollowing.update_and_alert(user)


@background(queue="peachjam", schedule=5 * 60, remove_existing_tasks=True)
def generate_judgment_summary(doc_id):
    from peachjam.models import Judgment

    doc = Judgment.objects.filter(id=doc_id).first()
    if not doc:
        log.info(f"No judgment with id {doc_id} exists, ignoring.")
        return
    log.info(f"Summarizing judgment {doc_id}")
    doc.generate_summary()
