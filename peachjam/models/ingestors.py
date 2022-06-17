from django.db import models
from django.utils import timezone

from peachjam.adapters import IndigoAdapter
from peachjam.tasks import update_document

ADAPTERS = {"indigo_adapter": IndigoAdapter}


class Ingestor(models.Model):

    ADAPTER_CHOICES = (("indigo_adapter", "Indigo Adapter"),)

    url = models.CharField(max_length=2048)
    token = models.CharField(max_length=2048)
    adapter = models.CharField(choices=ADAPTER_CHOICES, max_length=2048)
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
        # TODO: settings
        return ADAPTERS[self.adapter](self.url, self.token)
