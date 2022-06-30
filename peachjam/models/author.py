from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=255, null=False, unique=True)
    code = models.SlugField(max_length=255, unique=True)

    # TODO: Have author_types?

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"
