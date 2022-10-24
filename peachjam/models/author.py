from django.db import models
from django.utils.translation import gettext as _


class Author(models.Model):
    model_label = _("Author")

    name = models.CharField(max_length=255, null=False, unique=True)
    code = models.SlugField(max_length=255, null=False, unique=True)

    # TODO: Have author_types?

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"
