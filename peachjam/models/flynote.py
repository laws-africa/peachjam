"""Flynote model for judgment topic hierarchy.

Flynotes are hierarchical topics derived from judgment flynote text (e.g.
"Criminal law — sentencing — trial within a trial"). This model is separate
from Taxonomy to avoid loading huge trees into memory on sites like Tanzlii.

Uses path-based hierarchy (path = slug segments joined by "/") for efficient
queries without tree traversal.
"""

import logging

from django.db import connection, models, transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

log = logging.getLogger(__name__)

__all__ = ["Flynote", "JudgmentFlynote", "FlynoteDocumentCount"]


class Flynote(models.Model):
    """Hierarchical flynote topic, path-based for scalable queries."""

    name = models.CharField(_("name"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=1024)
    path = models.CharField(
        _("path"),
        max_length=2048,
        unique=True,
        db_index=True,
        help_text=_("Slug path from root, e.g. 'criminal-law/sentencing'."),
    )
    depth = models.PositiveIntegerField(
        _("depth"),
        default=0,
        db_index=True,
        help_text=_("0 = top level, 1 = one level down, etc."),
    )

    class Meta:
        ordering = ["path"]
        verbose_name = _("flynote")
        verbose_name_plural = _("flynotes")

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("flynote_topic_detail", kwargs={"topic_path": self.path})

    def get_children(self):
        """Direct children only. Single query, no tree load."""
        if self.path:
            prefix = self.path + "/"
        else:
            prefix = ""
        return Flynote.objects.filter(
            path__startswith=prefix, depth=self.depth + 1
        ).exclude(path=self.path)

    def get_descendants(self):
        """All descendants. Single query by path prefix."""
        if not self.path:
            return Flynote.objects.exclude(path="")
        return Flynote.objects.filter(path__startswith=self.path + "/")

    def get_ancestors(self):
        """Ancestors from root to parent. Queries by path prefix."""
        if not self.path or "/" not in self.path:
            return Flynote.objects.none()
        parts = self.path.split("/")[:-1]
        ancestor_paths = ["/".join(parts[: i + 1]) for i in range(len(parts))]
        return Flynote.objects.filter(path__in=ancestor_paths).order_by("depth")


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
    def refresh_for_flynote(cls, flynote):
        """Recompute document counts for this flynote and all its descendants."""
        if flynote is None:
            return

        prefix = flynote.path + "/" if flynote.path else ""
        path_pattern = prefix + "%"

        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM peachjam_flynotedocumentcount
                    WHERE flynote_id IN (
                        SELECT id FROM peachjam_flynote
                        WHERE path = %s OR path LIKE %s
                    )
                    """,
                    [flynote.path, path_pattern],
                )

                cursor.execute(
                    """
                    INSERT INTO peachjam_flynotedocumentcount (flynote_id, count)
                    SELECT
                        ancestor.id,
                        COUNT(DISTINCT jf.document_id)
                    FROM peachjam_flynote ancestor
                    INNER JOIN peachjam_flynote descendant
                        ON descendant.path = ancestor.path
                        OR descendant.path LIKE ancestor.path || '/%%'
                    INNER JOIN peachjam_judgmentflynote jf
                        ON jf.flynote_id = descendant.id
                    WHERE ancestor.path = %s OR ancestor.path LIKE %s
                    GROUP BY ancestor.id
                    """,
                    [flynote.path, path_pattern],
                )

        log.info(
            "Refreshed document counts for flynote '%s' (pk=%s)",
            flynote.slug,
            flynote.pk,
        )
