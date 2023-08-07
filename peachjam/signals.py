import sentry_sdk
from background_task.signals import (
    task_error,
    task_finished,
    task_started,
    task_successful,
)
from django.db.models import signals
from django.dispatch import receiver

from peachjam.models import CoreDocument, SourceFile, Work
from peachjam.tasks import update_extracted_citations_for_a_work


# monitor background tasks with sentry
@receiver(task_started)
def bg_task_started(sender, **kwargs):
    transaction = sentry_sdk.start_transaction(op="queue.task.bg")
    transaction.set_tag("transaction_type", "task")
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


@receiver(signals.post_save)
def doc_saved_update_language(sender, instance, **kwargs):
    """Update language list on related work when a subclass of CoreDocument is saved."""
    if isinstance(instance, CoreDocument) and not kwargs["raw"]:
        instance.work.update_languages()


@receiver(signals.post_delete)
def doc_deleted_update_language(sender, instance, **kwargs):
    """Update language list on related work after a subclass of CoreDocument is deleted."""
    if isinstance(instance, CoreDocument):
        # get by foreign key, because the actual instance in the db is now gone
        work = Work.objects.filter(pk=instance.work_id).first()
        if work:
            work.update_languages()


@receiver(signals.post_save)
def doc_saved_update_extracted_citations(sender, instance, **kwargs):
    """Update extracted citations when a subclass of CoreDocument is saved."""
    if isinstance(instance, CoreDocument) and not kwargs["raw"]:
        update_extracted_citations_for_a_work(instance.work_id)


@receiver(signals.post_delete)
def doc_deleted_update_extracted_citations(sender, instance, **kwargs):
    """Update language list on related work after a subclass of CoreDocument is deleted."""
    if isinstance(instance, CoreDocument):
        update_extracted_citations_for_a_work(instance.work_id)


@receiver(signals.post_save, sender=SourceFile)
def convert_to_pdf(sender, instance, created, **kwargs):
    """Convert a source file to PDF when it's saved"""
    if created:
        instance.ensure_file_as_pdf()
