from django.db import models

class Judge(models.Model):
    """
    This models represents judges.
    """
    name = models.CharField(max_length=1024, null=False, blank=False)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
