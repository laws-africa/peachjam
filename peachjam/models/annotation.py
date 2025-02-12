from django.db import models
from django.utils.translation import gettext_lazy as _


class Annotation(models.Model):
    document = models.ForeignKey(
        "peachjam.CoreDocument",
        related_name="annotations",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    text = models.TextField(_("text"), null=False, blank=False)
    target_id = models.CharField(_("target id"), max_length=1024, null=True, blank=True)
    target_selectors = models.JSONField(
        verbose_name=_("target selectors"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("annotation")
        verbose_name_plural = _("annotations")

    def __str__(self):
        return f"Annotation for {self.document}"
