from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from .core_document_model import CoreDocument

User = get_user_model()


class Folder(models.Model):
    name = models.CharField(_("name"), max_length=1024)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user_profile"),
        related_name="folders",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("folder")
        verbose_name_plural = _("folders")

    def __str__(self):
        return f"{self.name}"


class SavedDocument(models.Model):
    document = models.ForeignKey(CoreDocument, on_delete=models.CASCADE)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user_profile"),
        related_name="saved_documents",
    )
    folder = models.ForeignKey(
        Folder,
        on_delete=models.CASCADE,
        verbose_name=_("folder"),
        null=True,
        related_name="saved_documents",
    )

    class Meta:
        ordering = ("document__title",)
        verbose_name = _("saved document")
        verbose_name_plural = _("saved documents")
        unique_together = ("document", "folder")

    def __str__(self):
        message = f"{self.document.title} has been saved"
        if self.folder:
            message += f" to the '{self.folder.name}' folder"
        return message