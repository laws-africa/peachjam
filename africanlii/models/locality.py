from django.db import models
from countries_plus.models import Country

class Locality(models.Model):
    name = models.CharField(max_length=255, null=False)
    jurisdiction = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'localities'
        ordering = ['name']
        unique_together = ['name', 'jurisdiction']

    def __str__(self):
        return f'{self.name}'
