from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from peachjam.models import CoreDocument


class Taxonomy(MP_Node):
    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, unique=True)
    node_order_by = ["name"]
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )

    class Meta:
        verbose_name = _("taxonomies")
        verbose_name_plural = _("taxonomies")

    def __str__(self):
        return self.name

    def get_entity_profile(self):
        """Get the entity profile for this taxonomy, starting with the current taxonomy and then
        looking up the tree until one is found."""
        entity_profile = self.entity_profile.first()
        if entity_profile:
            return entity_profile
        if self.is_root():
            return None
        return self.get_parent().get_entity_profile()

    def save(self, *args, **kwargs):
        parent = self.get_parent()
        self.slug = (f"{parent.slug}-" if parent else "") + slugify(self.name)
        super().save(*args, **kwargs)


class DocumentTopic(models.Model):
    document = models.ForeignKey(
        CoreDocument,
        related_name="taxonomies",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    topic = models.ForeignKey(
        Taxonomy, on_delete=models.CASCADE, verbose_name=_("topic")
    )

    class Meta:
        ordering = ["topic"]
        verbose_name = _("document topic")
        verbose_name_plural = _("document topics")

    def __str__(self):
        return f"{self.topic.name} - {self.document.title}"
