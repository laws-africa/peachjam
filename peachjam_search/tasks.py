import logging

from background_task import background
from django.apps import apps
from django_elasticsearch_dsl.apps import DEDConfig
from django_elasticsearch_dsl.signals import (
    BaseSignalProcessor,
    RealTimeSignalProcessor,
)

from peachjam.models import CoreDocument

log = logging.getLogger(__name__)


class BackgroundTaskSearchProcessor(RealTimeSignalProcessor):
    """Processes django-elasticsearch-dsl indexing tasks with django-background-tasks.

    We only do save() in the background -- delete and pre_delete must happen in the main thread
    while the data is still available.
    """

    def handle_save(self, sender, instance, **kwargs):
        if not DEDConfig.autosync_enabled() or kwargs.get("raw"):
            return

        # this assumes that only documents are being indexed with elasticsearch
        if isinstance(instance, CoreDocument):
            search_model_saved(sender._meta.label, instance.pk)


def get_processor():
    config = apps.get_app_config("django_elasticsearch_dsl")
    return BaseSignalProcessor(config.signal_processor.connections)


@background(remove_existing_tasks=True)
def search_model_saved(model_name, pk):
    model = apps.get_model(model_name)
    instance = model.objects.filter(pk=pk).first()
    if not instance:
        log.info(f"Model {model_name} with pk {pk} does not exist. Ignoring task.")
        return

    get_processor().handle_save(model_name, instance)
