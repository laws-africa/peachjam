from django.db import models
from django.utils.text import slugify
from treebeard.mp_tree import MP_Node

from peachjam.models import CoreDocument


class Taxonomy(MP_Node):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    node_order_by = ["name"]

    class Meta:
        verbose_name_plural = "Taxonomies"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class DocumentTopic(models.Model):
    document = models.ForeignKey(CoreDocument, on_delete=models.CASCADE)
    topic = models.ForeignKey(Taxonomy, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Document Topics"

    def __str__(self):
        return f"{self.topic.name} - {self.document.title}"
