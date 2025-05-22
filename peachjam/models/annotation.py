from django.conf import settings
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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="annotations",
        on_delete=models.CASCADE,
        verbose_name=_("user"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("annotation")
        verbose_name_plural = _("annotations")

    def friendly_target(self):
        """A human-friendly rendering of the target's title."""
        if self.target_id:
            if self.target_id.startswith("page-"):
                return _("Page") + " " + self.target_id.split("-")[1]
            return self.document.friendly_provision_title(self.target_id)

    def __str__(self):
        return f"Annotation for {self.document}"
