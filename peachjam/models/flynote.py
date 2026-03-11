"""Flynote model for judgment topic hierarchy.

Flynotes are hierarchical topics derived from judgment flynote text (e.g.
"Criminal law — sentencing — trial within a trial"). This model is separate
from Taxonomy to avoid loading huge trees into memory on sites like Tanzlii.

Extends treebeard's MP_Node (materialised path) for efficient hierarchical
queries, just like the Taxonomy model.
"""

import logging

from django.db import connection, models, transaction
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from treebeard.mp_tree import MP_Node

log = logging.getLogger(__name__)

__all__ = ["Flynote", "JudgmentFlynote", "FlynoteDocumentCount"]


class Flynote(MP_Node):
    """Hierarchical flynote topic using treebeard's materialised path."""

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=1024, unique=True)
    node_order_by = ["name"]

    class Meta:
        verbose_name = _("flynote")
        verbose_name_plural = _("flynotes")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("flynote_topic_detail", kwargs={"slug": self.slug})

    def update_slug(self):
        """Build a unique slug from the ancestor chain, just like Taxonomy."""
        old_slug = self.slug
        parent = self.get_parent()
        self.slug = (f"{parent.slug}-" if parent else "") + slugify(self.name)
        return old_slug != self.slug

    def save(self, *args, **kwargs):
        self.update_slug()
        super().save(*args, **kwargs)


class JudgmentFlynote(models.Model):
    """Links a judgment to a flynote topic (leaf node)."""

    document = models.ForeignKey(
        "peachjam.Judgment",
        related_name="flynotes",
        on_delete=models.CASCADE,
        verbose_name=_("judgment"),
    )
    flynote = models.ForeignKey(
        Flynote,
        on_delete=models.CASCADE,
        related_name="judgments",
        verbose_name=_("flynote"),
    )

    class Meta:
        ordering = ["flynote"]
        verbose_name = _("judgment flynote")
        verbose_name_plural = _("judgment flynotes")
        unique_together = ("document", "flynote")

    def __str__(self):
        return f"{self.flynote.name} - {self.document.title}"


class FlynoteDocumentCount(models.Model):
    """Pre-calculated count of judgments linked to a flynote and its descendants."""

    flynote = models.OneToOneField(
        Flynote,
        on_delete=models.CASCADE,
        related_name="document_count_cache",
        verbose_name=_("flynote"),
    )
    count = models.PositiveIntegerField(_("count"), default=0)

    class Meta:
        verbose_name = _("flynote document count")
        verbose_name_plural = _("flynote document counts")

    def __str__(self):
        return f"{self.flynote.name}: {self.count}"

    @classmethod
    def refresh_for_flynote(cls, root):
        """Recompute document counts for flynotes under *root*.

        Each node's count includes documents linked directly to it plus
        documents linked to any of its descendants. Uses treebeard's
        materialised path to walk ancestors efficiently in a single SQL
        query, following the same pattern as TaxonomyDocumentCount.
        """
        if root is None:
            raise ValueError("refresh_for_flynote requires a root flynote node")

        root_path = root.path

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM peachjam_flynotedocumentcount
                    WHERE flynote_id IN (
                        SELECT id FROM peachjam_flynote
                        WHERE path LIKE %s
                    )
                    """,
                    [root_path + "%"],
                )

                cursor.execute(
                    """
                    INSERT INTO peachjam_flynotedocumentcount (flynote_id, count)
                    SELECT
                        ancestor.id,
                        COUNT(DISTINCT jf.document_id)
                    FROM peachjam_flynote ancestor
                    INNER JOIN peachjam_flynote descendant
                        ON descendant.path LIKE ancestor.path || '%%'
                        AND descendant.path LIKE %s
                    INNER JOIN peachjam_judgmentflynote jf
                        ON jf.flynote_id = descendant.id
                    WHERE ancestor.path LIKE %s
                    GROUP BY ancestor.id
                    """,
                    [root_path + "%", root_path + "%"],
                )

        log.info(
            "Refreshed document counts for flynote tree rooted at '%s' (pk=%s)",
            root.slug,
            root.pk,
        )

    @classmethod
    def refresh_for_all_flynotes(cls):
        """Recompute document counts for each flynote tree independently."""
        refreshed = 0
        for root in Flynote.get_root_nodes():
            cls.refresh_for_flynote(root)
            refreshed += 1

        log.info(
            "Refreshed document counts for all flynotes across %d roots.",
            refreshed,
        )
