from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse


class DocumentAccessGroup(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        verbose_name="group",
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "document access group"
        verbose_name_plural = "document access groups"

    def __str__(self):
        return self.group.name

    def get_absolute_url(self):
        return reverse("document_access_group_detail", args=[self.pk])
