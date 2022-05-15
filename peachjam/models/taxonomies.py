from django.db import models
from treebeard.mp_tree import MP_Node

from peachjam.models import CoreDocument


class Taxonomy(MP_Node):
    name = models.CharField(max_length=255)
    node_order_by = ["name"]

    class Meta:
        verbose_name_plural = "Taxonomies"


class DocumentCategory(models.Model):
    document = models.ForeignKey(CoreDocument, on_delete=models.CASCADE)
    category = models.ForeignKey(Taxonomy, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Document Categories"
