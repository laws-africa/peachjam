from django.db import models
from django.utils import timezone

from peachjam.adapters import IndigoAdapter  # noqa
from peachjam.plugins import plugins
from peachjam.tasks import update_document


def adapter_choices():
    # TOOD: use these choices in the ingestor admin form
    return [(key, p.name) for key, p in plugins.registry["ingestor-adapter"].items()]


class AdapterSettings(models.Model):
    token = models.CharField(max_length=255)
    url = models.URLField()
    ingestor = models.ForeignKey("peachjam.Ingestor", on_delete=models.CASCADE)


class Ingestor(models.Model):
    # TODO: add a name field
    # url = models.CharField(max_length=2048)
    # token = models.CharField(max_length=2048)
    adapter = models.CharField(max_length=2048)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.adapter}"

    def check_for_updates(self):
        adapter = self.get_adapter()
        docs = adapter.check_for_updates(self.last_refreshed_at)
        for doc in docs:
            # queue up a background task to update this document
            update_document(self.id, doc)

        self.last_refreshed_at = timezone.now()
        self.save()

    def update_document(self, document_id):
        adapter = self.get_adapter()
        adapter.update_document(document_id)

    def get_adapter(self):
        klass = plugins.registry["ingestor-adapter"][self.adapter]
        settings = AdapterSettings.objects.filter(ingestor=self).first()
        return klass(settings.url, settings.token)
