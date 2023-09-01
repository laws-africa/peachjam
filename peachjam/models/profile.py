from countries_plus.models import Country
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


def entity_profile_photo_filename(instance, filename):
    return f"media/entity_profile/{instance.content_type.model}/{instance.object_id}/{filename}"


class EntityProfile(models.Model):
    about_html = models.TextField(_("about HTML"), null=True, blank=True)
    website_url = models.URLField(_("website URL"), null=True, blank=True)
    address = models.TextField(_("address"), null=True, blank=True)
    profile_photo = models.ImageField(
        upload_to=entity_profile_photo_filename,
        null=True,
        blank=True,
        verbose_name=_("profile photo"),
    )
    background_photo = models.ImageField(
        upload_to=entity_profile_photo_filename,
        null=True,
        blank=True,
        verbose_name=_("background photo"),
    )

    # generic relation details
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        unique_together = ("content_type", "object_id")
        verbose_name = _("profile")
        verbose_name_plural = _("profile")

    def __str__(self):
        return f"{self.content_type.model} - #{self.object_id} profile"


class JurisdictionProfile(models.Model):
    jurisdiction = models.OneToOneField(
        Country, on_delete=models.PROTECT, verbose_name=_("jurisdiction")
    )
    entity_profile = GenericRelation(EntityProfile, verbose_name=_("profile"))

    class Meta:
        verbose_name = _("jurisdiction profile")
        verbose_name_plural = _("jurisdiction profiles")

    def __str__(self):
        return f"{self.jurisdiction} profile"
