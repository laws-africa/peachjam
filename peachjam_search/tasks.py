import logging

from background_task import background
from django.apps import apps
from django_elasticsearch_dsl.apps import DEDConfig
from django_elasticsearch_dsl.signals import (
    BaseSignalProcessor,
    RealTimeSignalProcessor,
)

from peachjam.models import CoreDocument
from peachjam_search.documents import SearchableDocument

log = logging.getLogger(__name__)


class BackgroundTaskSearchProcessor(RealTimeSignalProcessor):
    """Processes django-elasticsearch-dsl indexing tasks with django-background-tasks.

    We only do save() in the background -- delete and pre_delete must happen in the main thread
    while the data is still available.
    """

    def handle_save(self, sender, instance, **kwargs):
        self.update_if_core_document(sender, instance, **kwargs)

    def handle_pre_delete(self, sender, instance, **kwargs):
        # an instance of a model potentially related to a CoreDocument (but not a CoreDocument itself) is being deleted
        # if it's related, queue up a re-index of the CoreDocument
        self.update_if_core_document(sender, instance, **kwargs)

    def update_if_core_document(self, sender, instance, **kwargs):
        """If the instance is a CoreDocument or a model related to a CoreDocument, queue up a re-index."""
        if not DEDConfig.autosync_enabled() or kwargs.get("raw"):
            return

        # Check if instance is in the list of related models or is a CoreDocument,
        related_models = SearchableDocument.django.related_models
        if any(isinstance(instance, cls) for cls in [CoreDocument, *related_models]):
            # queue up the task for 60 seconds from now, so that quick edits to the document don't all trigger
            # a re-index
            search_model_saved(instance.__class__._meta.label, instance.pk, schedule=60)


def get_processor():
    config = apps.get_app_config("django_elasticsearch_dsl")
    return BaseSignalProcessor(config.signal_processor.connections)


@background(queue="peachjam", remove_existing_tasks=True)
def search_model_saved(model_name, pk):
    model = apps.get_model(model_name)
    instance = model.objects.filter(pk=pk).first()
    if not instance:
        log.info(f"Model {model_name} with pk {pk} does not exist. Ignoring task.")
        return

    get_processor().handle_save(model_name, instance)
