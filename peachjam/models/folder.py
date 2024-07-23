from django.db import models
from django.utils.translation import gettext_lazy as _

from .core_document_model import CoreDocument


class Folder(models.Model):
    name = models.CharField(_("name"), max_length=1024)
    user_profile = models.ForeignKey(
        "peachjam.UserProfile",
        on_delete=models.CASCADE,
        verbose_name=_("user_profile"),
        related_name="folders",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("folder")
        verbose_name_plural = _("folders")
        unique_together = ("name", "user_profile")

    def __str__(self):
        return f"{self.name}"


class SavedDocument(models.Model):
    document = models.ForeignKey(CoreDocument, on_delete=models.CASCADE)
    user_profile = models.ForeignKey(
        "peachjam.UserProfile",
        on_delete=models.CASCADE,
        verbose_name=_("user_profile"),
        related_name="saved_documents",
    )
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, verbose_name=_("folder"), null=True
    )

    class Meta:
        ordering = ("document__title",)
        verbose_name = _("saved document")
        verbose_name_plural = _("saved documents")
        unique_together = ("document", "folder")

    def __str__(self):
        return f"{self.document.title}"
