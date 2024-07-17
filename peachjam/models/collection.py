import os

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from .core_document_model import CoreDocument

User = get_user_model()


def file_location(instance, filename):
    filename = os.path.basename(filename)
    return f"{instance.SAVE_FOLDER}/{instance.pk}/{filename}"


class Collection(models.Model):
    name = models.CharField(_("name"), max_length=1024, unique=True)
    user_profile = models.ForeignKey(
        "peachjam.UserProfile",
        on_delete=models.CASCADE,
        verbose_name=_("user_profile"),
        related_name="collections",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = _("collection")
        verbose_name_plural = _("collections")

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
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, verbose_name=_("collection"), null=True
    )

    class Meta:
        ordering = ("document__title",)
        verbose_name = _("saved document")
        verbose_name_plural = _("saved documents")

    def __str__(self):
        return f"{self.document.title}"
