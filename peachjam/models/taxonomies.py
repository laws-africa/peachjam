from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from guardian.shortcuts import get_objects_for_user
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
    restricted = models.BooleanField(
        _("restricted"),
        default=False,
        null=False,
    )
    show_in_document_listing = models.BooleanField(
        _("show in document listing"),
        default=False,
        null=False,
        help_text=_(
            "Show this taxonomy in the document listing page? Cascades to descendents."
        ),
    )
    allow_offline = models.BooleanField(
        _("allow offline access"),
        default=False,
        null=False,
        help_text=_(
            "Allow users to make this taxonomy and its descendants available offline."
        ),
    )

    class Meta:
        verbose_name = _("taxonomy")
        verbose_name_plural = _("taxonomies")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(
            "taxonomy_detail",
            kwargs={"topic": self.get_root().slug, "child": self.slug},
        )

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

    def get_allowed_children(self, user):
        if user.is_authenticated:
            allowed_taxonomies = set(
                get_objects_for_user(user, "peachjam.view_taxonomy").values_list(
                    "id", flat=True
                )
            )
        else:
            allowed_taxonomies = []

        children = self.get_children().values("id", "restricted")
        exclude = []

        for child in children:
            is_restricted = child["restricted"]
            is_allowed = child["id"] in allowed_taxonomies
            if is_restricted and not is_allowed:
                exclude.append(child["id"])

        children = self.get_children().exclude(id__in=exclude)
        return children

    def get_offline_ancestor(self):
        """Return the first ancestor which is available offline, including this node, if any."""
        if self.allow_offline:
            return self
        return self.get_ancestors().filter(allow_offline=True).first()

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

    @classmethod
    def get_allowed_taxonomies(cls, user, root=None):
        if user.is_authenticated:
            allowed_taxonomies = set(
                get_objects_for_user(user, "peachjam.view_taxonomy").values_list(
                    "id", flat=True
                )
            )
        else:
            allowed_taxonomies = []

        node_ids = []

        def filter_nodes(node):
            is_restricted = node.get("data", {}).get("restricted", False)
            is_allowed = node.get("id") in allowed_taxonomies
            if is_restricted and not is_allowed:
                return None

            node_ids.append(node["id"])

            if "children" in node:
                filtered_children = [
                    child
                    for child in (filter_nodes(child) for child in node["children"])
                    if child is not None
                ]
                if filtered_children:
                    node["children"] = filtered_children
                else:
                    node.pop("children", None)
            return node

        # Filter the tree
        if root:
            taxonomies = root.dump_bulk(root)
        else:
            taxonomies = cls.dump_bulk()
        filtered_taxonomies = [
            filtered_node
            for filtered_node in (filter_nodes(node) for node in taxonomies)
            if filtered_node is not None
        ]
        return {
            "tree": filtered_taxonomies,
            "pk_list": node_ids,
        }

    @classmethod
    def limit_to_lowest(cls, topics):
        """Limit the topics to the lowest level of the tree. This is used to avoid a document being tagged under
        a parent and a descendant taxonomy topic."""

        # walk bottom up and exclude topics that already have a descendant selected
        selected = []
        for topic in sorted(topics, key=lambda topic: topic.depth, reverse=True):
            if not any(t.path.startswith(topic.path) for t in selected):
                selected.append(topic)

        return selected


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
