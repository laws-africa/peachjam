import os
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from languages_plus.models import Language


def file_location(instance, filename):
    filename = os.path.basename(filename)
    return f"{instance.SAVE_FOLDER}/{instance.pk}/{filename}"


class UserProfile(models.Model):
    SAVE_FOLDER = "user_profiles"

    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, verbose_name=_("user")
    )
    photo = models.ImageField(
        _("photo"), upload_to=file_location, blank=True, null=True
    )
    profile_description = models.TextField(_("profile description"))
    tracking_id = models.UUIDField(_("tracking id"), default=uuid.uuid4, editable=False)

    preferred_language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        default="en",
        related_name="+",
        verbose_name=_("preferred language"),
    )
    accepted_terms_at = models.DateTimeField(
        _("accepted terms at"),
        default=timezone.now,
        help_text=_("When the user accepted the terms of service."),
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)
    deleted_reason = models.TextField(_("deleted reason"), null=True, blank=True)
    email_hash = models.CharField(_("email hash"), max_length=64, null=True, blank=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    @property
    def tracking_id_str(self):
        return str(self.tracking_id)

    def is_primary_email_verified(self):
        return self.user.emailaddress_set.filter(
            verified=True, email=self.user.email
        ).exists()

    def avatar_url(self):
        """Returns the URL of the first social account avatar, if any."""
        for social_account in self.user.socialaccount_set.all():
            if social_account.extra_data.get("picture"):
                return social_account.extra_data.get("picture")

    def __str__(self):
        return f"{self.user.username}"
