import logging

from django.db import models
from django.utils import timezone

from peachjam.plugins import plugins
from peachjam.tasks import update_document

log = logging.getLogger(__name__)


class IngestorSetting(models.Model):
    name = models.CharField(max_length=2048)
    value = models.CharField(max_length=2048)
    ingestor = models.ForeignKey("peachjam.Ingestor", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} = {self.value}"


class Ingestor(models.Model):
    adapter = models.CharField(max_length=2048)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def check_for_updates(self):
        adapter = self.get_adapter()
        log.info(
            f"Checking for ingestor updates for {self}, last_refresh_at {self.last_refreshed_at}"
        )
        docs = adapter.check_for_updates(self.last_refreshed_at)
        log.info(f"{len(docs)} documents to update")
        for doc in docs:
            update_document(self.id, doc)

        self.last_refreshed_at = timezone.now()
        self.save()
        log.info(f"Finished checking for ingestor updates for {self}")

    def update_document(self, document_id):
        adapter = self.get_adapter()
        adapter.update_document(document_id)

    def get_adapter(self):
        klass = plugins.registry["ingestor-adapter"][self.adapter]
        ingestor_settings = IngestorSetting.objects.filter(ingestor=self)
        settings = {s.name: s.value for s in ingestor_settings}
        return klass(settings)
