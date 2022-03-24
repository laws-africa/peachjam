from django.db import models

class AuthoringBody(models.Model):
  """
  This models represents authoring bodies.
  """
  name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
  description = models.TextField(blank=True)

  def __str__(self):
    return self.name
