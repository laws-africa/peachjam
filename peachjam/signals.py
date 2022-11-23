import sentry_sdk
from background_task.signals import (
    task_error,
    task_finished,
    task_started,
    task_successful,
)
from django.db.models import signals
from django.dispatch import receiver

from peachjam.models import CoreDocument


# monitor background tasks with elastic-apm
@receiver(task_started)
def bg_task_started(sender, **kwargs):
    transaction = sentry_sdk.start_transaction(op="task")
    # fake an entry into the context
    transaction.__enter__()


@receiver(task_successful)
def bg_task_success(sender, completed_task, **kwargs):
    transaction = sentry_sdk.Hub.current.scope.transaction
    if transaction:
        transaction.name = completed_task.task_name


@receiver(task_error)
def bg_task_error(sender, task, **kwargs):
    transaction = sentry_sdk.Hub.current.scope.transaction
    if transaction:
        transaction.name = task.task_name

    # report error to sentry
    sentry_sdk.capture_exception()


@receiver(task_finished)
def bg_task_finished(sender, **kwargs):
    transaction = sentry_sdk.Hub.current.scope.transaction
    if transaction:
        # fake an exit from the transaction context
        transaction.__exit__(None, None, None)


@receiver(signals.post_save, sender=CoreDocument)
def update_language(sender, instance, **kwargs):
    if not kwargs["raw"]:
        instance.work.languages = [instance.language.iso_639_3]
        instance.work.save()
