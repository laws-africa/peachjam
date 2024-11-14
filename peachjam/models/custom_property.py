from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomPropertyLabel(models.Model):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = _("custom property label")
        verbose_name_plural = _("custom property labels")
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomProperty(models.Model):
    document = models.ForeignKey(
        "peachjam.CoreDocument",
        on_delete=models.CASCADE,
        related_name="custom_properties",
    )
    label = models.ForeignKey(
        CustomPropertyLabel, on_delete=models.CASCADE, related_name="+"
    )
    value = models.CharField(max_length=4096, null=True, blank=True)

    class Meta:
        verbose_name = _("custom property")
        verbose_name_plural = _("custom properties")
        ordering = ["label"]

    def __str__(self):
        return f"{self.label}: {self.value}"
