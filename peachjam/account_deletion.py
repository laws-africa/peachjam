import hashlib

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from peachjam.customerio import get_customerio
from peachjam.models import (
    Annotation,
    DocumentChatThread,
    Folder,
    SavedDocument,
    UserFollowing,
)
from peachjam_search.models import SavedSearch
from peachjam_subs.models import Subscription

User = get_user_model()


def hashed_email(email):
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


@transaction.atomic
def delete_and_anonymise_user(user, deleted_reason):
    profile = user.userprofile
    original_email = user.email or ""

    # Step 1: remove user-generated content.
    Annotation.objects.filter(user=user).delete()
    UserFollowing.objects.filter(user=user).delete()
    SavedSearch.objects.filter(user=user).delete()
    SavedDocument.objects.filter(user=user).delete()
    Folder.objects.filter(user=user).delete()
    DocumentChatThread.objects.filter(user=user).delete()

    # Billing/subscription records.
    Subscription.objects.filter(user=user).delete()

    # Remove from customer.io before identifiers are removed.
    get_customerio().track_user_deleted(user)

    # Step 2: anonymise and remove PII.
    profile.deleted_at = timezone.now()
    profile.deleted_reason = deleted_reason
    profile.email_hash = hashed_email(original_email) if original_email else None
    profile.photo.delete(save=False)
    profile.photo = None
    profile.profile_description = ""
    profile.save()

    EmailAddress.objects.filter(user=user).delete()
    SocialToken.objects.filter(account__user=user).delete()
    SocialAccount.objects.filter(user=user).delete()

    user.username = f"deleted-{user.pk}"
    user.first_name = ""
    user.last_name = ""
    user.email = ""
    user.is_active = False
    user.set_unusable_password()
    user.save()

    return user
