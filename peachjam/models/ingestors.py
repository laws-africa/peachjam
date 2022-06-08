from django.db import models

from peachjam.adapters import IndigoAdapter

ADAPTERS = {"indigo_adapter": IndigoAdapter}


class Ingestor(models.Model):

    ADAPTER_CHOICES = (("indigo_adapter", "Indigo Adapter"),)

    url = models.CharField(max_length=2048)
    token = models.CharField(max_length=2048)
    adapter = models.CharField(choices=ADAPTER_CHOICES, max_length=2048)
    last_refreshed_at = models.DateTimeField()

    def __str__(self):
        return f"{self.adapter}"
