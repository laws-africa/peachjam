from django.db import models

class DocumentNature(models.Model):
  """
  This models represents document nature.
  """

  name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
  description = models.TextField(blank=True)

  def __str__(self):
    return self.name
