import logging

import sentry_sdk
from background_task import background
from background_task.signals import task_error, task_started, task_successful
from django.apps import apps
from django.dispatch import receiver

log = logging.getLogger(__name__)


def get_elasticapm_client():
    try:
        return apps.get_app_config("elasticapm").client
    except LookupError:
        log.warning(
            "Django app elasticapm not installed. Background tasks will not have metrics."
        )
        return None


@background(remove_existing_tasks=True)
def update_document(ingestor_id, document_id):
    from peachjam.models import Ingestor

    ingestor = Ingestor.objects.filter(pk=ingestor_id).first()
    if not ingestor:
        log.info(f"No ingestor with id {ingestor_id} exists, ignoring.")
        return

    log.info(f"Updating document {document_id} with ingestor {ingestor}")
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


# monitor background tasks with elastic-apm
@receiver(task_started)
def bg_task_started(sender, **kwargs):
    client = get_elasticapm_client()
    if client:
        client.begin_transaction(transaction_type="task")


@receiver(task_successful)
def bg_task_success(sender, completed_task, **kwargs):
    client = get_elasticapm_client()
    if client:
        client.end_transaction(name=completed_task.task_name, result="success")


@receiver(task_error)
def bg_task_error(sender, task, **kwargs):
    # report errors to elasticapm
    client = get_elasticapm_client()
    if client:
        client.capture_exception()
        client.end_transaction(name=task.task_name, result="error")

    # report errors to sentry
    with sentry_sdk.push_scope() as scope:
        scope.transaction = task.task_name
        sentry_sdk.capture_exception()
