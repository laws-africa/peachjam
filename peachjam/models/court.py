from django.db import models
from countries_plus.models import Country
      
class Court(models.Model):
    name = models.CharField(max_length=255, null=False)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'courts'
        ordering = ['name']
        unique_together = ['name', 'country']

    def __str__(self):
        return f'{self.name}'
