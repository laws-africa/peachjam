from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

from peachjam.models import CoreDocument


class Taxonomy(MP_Node):
    name = models.CharField(_("name"), max_length=255)
    path_name = models.CharField(_("path name"), max_length=4096, blank=True)
    slug = models.SlugField(_("slug"), max_length=10 * 1024, unique=True)
    node_order_by = ["name"]
    entity_profile = GenericRelation(
        "peachjam.EntityProfile", verbose_name=_("profile")
    )
    show_in_document_listing = models.BooleanField(
        _("show in document listing"),
        default=False,
        null=False,
        help_text=_(
            "Show this taxonomy in the document listing page? Cascades to descendents."
        ),
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

    def update_slug(self):
        old_slug = self.slug
        parent = self.get_parent()
        self.slug = (f"{parent.slug}-" if parent else "") + slugify(
            self.name_en or self.name
        )
        return old_slug != self.slug

    def update_path_name(self):
        changed = False

        # we need to do this for each language field suffix
        suffixes = [""] + [f"_{x[0]}" for x in settings.LANGUAGES]
        for suffix in suffixes:
            name = getattr(self, f"name{suffix}", None)
            path_name_attr = f"path_name{suffix}"

            if name:
                old_path_name = getattr(self, path_name_attr)
                parts = [name]
                if not self.is_root() and not self.get_parent().is_root():
                    parent_path_name = (
                        getattr(self.get_parent(), path_name_attr, None)
                        or self.get_parent().path_name
                    )
                    parts.insert(0, parent_path_name)
                setattr(self, path_name_attr, " — ".join(parts))

                changed = changed or old_path_name != getattr(self, path_name_attr)
            elif getattr(self, path_name_attr):
                # the name has been cleared, so clear the path name
                setattr(self, path_name_attr, "")
                changed = True

        return changed

    def save(self, *args, **kwargs):
        changed = self.update_slug()
        changed = self.update_path_name() or changed

        super().save(*args, **kwargs)

        if changed:
            # update all our children to use the new slug
            for child in self.get_children():
                child.save()

    @classmethod
    def get_tree_for_items(cls, items):
        """Get a tree of taxonomies for a list of items, which can be leaf or intermediate nodes. The path
        from the root to each item is calculated and merged with the others."""
        tree = {}
        paths = [list(item.get_ancestors()) + [item] for item in items]

        for path in paths:
            current_level = tree
            for i, node in enumerate(path):
                # stash the root for use when building urls
                if i == 0:
                    root = node
                else:
                    node.root = root
                if node not in current_level:
                    current_level[node] = {}
                current_level = current_level[node]

        return tree


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
        unique_together = ("document", "topic")

    def __str__(self):
        return f"{self.topic.name} - {self.document.title}"
