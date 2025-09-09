from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls.base import reverse
from django.utils.translation import gettext_lazy as _

from .core_document import CoreDocument

User = get_user_model()


class Folder(models.Model):
    name = models.CharField(_("name"), max_length=100)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="folders",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("name",)
        verbose_name = _("folder")
        verbose_name_plural = _("folders")
        permissions = [("download", "Can download documents")]

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse("folder_list") + "#folder-" + str(self.pk)


class SavedDocument(models.Model):
    document = models.ForeignKey(
        CoreDocument, related_name="saved_documents", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name=_("user"),
        related_name="saved_documents",
    )
    folders = models.ManyToManyField(Folder, related_name="saved_documents")
    note = models.TextField(_("note"), null=True, blank=True, max_length=2048)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("document__title",)
        verbose_name = _("saved document")
        verbose_name_plural = _("saved documents")

    def can_save_more_documents(self):
        active_subscription = self.user.subscriptions.filter(status="active").first()
        if not active_subscription:
            return False
        limit = active_subscription.product_offering.product.saved_document_limit
        if limit < 0:
            return True
        count = self.user.saved_documents.count()
        return count <= limit

    def clean(self):
        if not self.can_save_more_documents():
            raise ValidationError("User has reached the limit of saved documents.")

    def delete(self, using=None, keep_parents=False):
        self.document.annotations.filter(user=self.user).delete()
        return super().delete(using=using, keep_parents=keep_parents)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
