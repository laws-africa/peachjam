from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class PublicGroup(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        verbose_name="group",
    )
    slug = models.SlugField(
        unique=True,
        verbose_name="slug",
        blank=True,
    )

    class Meta:
        verbose_name = "public group"
        verbose_name_plural = "public groups"

    def __str__(self):
        return self.group.name

    def get_absolute_url(self):
        return reverse("group_documents", args=[self.slug])

    def save(self, *args, **kwargs):
        self.slug = slugify(self.group.name)
        super().save(*args, **kwargs)
