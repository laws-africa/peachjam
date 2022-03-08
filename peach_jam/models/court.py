from django.db import models

class Country(models.Model):
    name = models.CharField(max_length=255, null=False, unique=True)
    code = models.CharField(max_length=20)
    header_title = models.CharField(max_length=255, null=False)

    class Meta:
        verbose_name_plural = 'countries'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'
      
class Court(models.Model):
    name = models.CharField(max_length=255, null=False, unique=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'courts'
        ordering = ['name']

    def __str__(self):
        return f'{self.name}'