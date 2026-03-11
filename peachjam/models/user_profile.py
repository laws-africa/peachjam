import hashlib
import os
import uuid

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from languages_plus.models import Language

from peachjam.customerio import get_customerio
from peachjam_search.models import SavedSearch
from peachjam_subs.models import Subscription

from .annotation import Annotation
from .chat import DocumentChatThread
from .save_document import Folder, SavedDocument
from .user_following import UserFollowing


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

    @staticmethod
    def hashed_email(email):
        return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()

    @transaction.atomic
    def delete_account(self, deleted_reason):
        original_email = self.user.email or ""

        Annotation.objects.filter(user=self.user).delete()
        UserFollowing.objects.filter(user=self.user).delete()
        SavedSearch.objects.filter(user=self.user).delete()
        SavedDocument.objects.filter(user=self.user).delete()
        Folder.objects.filter(user=self.user).delete()
        DocumentChatThread.objects.filter(user=self.user).delete()
        Subscription.objects.filter(user=self.user).delete()

        get_customerio().track_user_deleted(self.user)

        self.deleted_at = timezone.now()
        self.deleted_reason = deleted_reason
        self.email_hash = self.hashed_email(original_email) if original_email else None
        self.photo.delete(save=False)
        self.photo = None
        self.profile_description = ""
        self.save()

        EmailAddress.objects.filter(user=self.user).delete()
        SocialToken.objects.filter(account__user=self.user).delete()
        SocialAccount.objects.filter(user=self.user).delete()

        self.user.username = f"deleted-{self.user.pk}"
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.email = ""
        self.user.is_active = False
        self.user.set_unusable_password()
        self.user.save()

        return self.user

    def avatar_url(self):
        """Returns the URL of the first social account avatar, if any."""
        for social_account in self.user.socialaccount_set.all():
            if social_account.extra_data.get("picture"):
                return social_account.extra_data.get("picture")

    def __str__(self):
        return f"{self.user.username}"
