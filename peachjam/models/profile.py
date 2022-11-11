from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


def entity_profile_photo_filename(instance, filename):
    return f"media/entity_profile/{instance.content_type.model}/{instance.object_id}/{filename}"


class EntityProfile(models.Model):
    about_html = models.TextField(null=True, blank=True)
    website_url = models.URLField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    profile_photo = models.ImageField(
        upload_to=entity_profile_photo_filename, null=True, blank=True
    )
    background_photo = models.ImageField(
        upload_to=entity_profile_photo_filename, null=True, blank=True
    )

    # generic relation details
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = ("content_type", "object_id")
        verbose_name_plural = "Profile"

    def __str__(self):
        return f"{self.content_type.model} - #{self.object_id} profile"
