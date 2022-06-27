from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=255, null=False)
    code = models.SlugField(max_length=255)

    # TODO: Have author_types?

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"
