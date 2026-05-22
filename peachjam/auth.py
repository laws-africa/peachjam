import logging

from allauth.account.adapter import DefaultAccountAdapter, get_adapter
from allauth.account.internal.flows.code_verification import user_id_to_str
from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.utils import perform_login
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, OperationalError, ProgrammingError
from django.utils import translation
from templated_email import send_templated_mail

from peachjam.models import pj_settings
from peachjam.signals import password_reset_started

logger = logging.getLogger(__name__)

_original_send_by_email = LoginCodeVerificationProcess.send_by_email
_original_finish = LoginCodeVerificationProcess.finish


def _patched_send_by_email(self, email, **kwargs):
    adapter = get_adapter()
    code = adapter.generate_login_code()
    context = {
        "request": self.request,
        "code": code,
    }
    adapter.send_mail("account/email/login_code", email, context)
    self.state["code"] = code
    self.add_sent_message({"email": email, "recipient": email})


def _patched_finish(self, redirect_url):
    if not self.user:
        email = self.state.get("email")
        if email:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"username": email},
            )
            if created:
                user.set_unusable_password()
                user.save()
            self.state["user_id"] = user_id_to_str(user)
            self._user = user
    return _original_finish(self, redirect_url)


LoginCodeVerificationProcess.send_by_email = _patched_send_by_email
LoginCodeVerificationProcess.finish = _patched_finish


def get_all_users_permission_group_name():
    return settings.PEACHJAM.get("ALL_USERS_PERMISSION_GROUP", "All users")


def get_or_create_all_users_permission_group():
    group_name = get_all_users_permission_group_name()
    if not group_name:
        return None

    try:
        return Group.objects.get_or_create(name=group_name)[0]
    except IntegrityError:
        return Group.objects.get(name=group_name)
    except (OperationalError, ProgrammingError):
        logger.debug("Could not create all-users permission group", exc_info=True)
        return None


class AllUsersPermissionBackend(BaseBackend):
    """Grant a configured baseline group of permissions to every user."""

    def get_group_permissions(self, user_obj, obj=None):
        if obj is not None:
            return set()

        if not hasattr(user_obj, "_all_users_perm_cache"):
            group = get_or_create_all_users_permission_group()
            if group:
                perms = group.permissions.select_related("content_type")
                user_obj._all_users_perm_cache = {
                    f"{perm.content_type.app_label}.{perm.codename}" for perm in perms
                }
            else:
                user_obj._all_users_perm_cache = set()

        return user_obj._all_users_perm_cache

    def get_all_permissions(self, user_obj, obj=None):
        return self.get_group_permissions(user_obj, obj=obj)

    def has_perm(self, user_obj, perm, obj=None):
        return perm in self.get_all_permissions(user_obj, obj=obj)

    def has_module_perms(self, user_obj, app_label):
        return any(
            permission.startswith(f"{app_label}.")
            for permission in self.get_all_permissions(user_obj)
        )


def user_display(user):
    """Return the user's display name."""
    return user.get_full_name() or user.email or user.username


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return pj_settings().allow_signups

    def send_mail(self, template_prefix, email, context):
        # injection point for hooking into password reset initiation
        # see allauth.account.forms.ResetPasswordForm._send_password_reset_mail
        if template_prefix == "account/email/password_reset_key":
            user = context["user"]
            password_reset_started.send(
                sender=user.__class__,
                request=context["request"],
                user=user,
            )

        user = context.get("user")
        language = None

        if user:
            profile = getattr(user, "user_profile", None)
            preferred_language = getattr(profile, "preferred_language", None)

            if preferred_language:
                language = preferred_language.pk

        mail_kwargs = dict(
            template_name=template_prefix,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            context=context,
        )

        if language:
            with translation.override(language):
                send_templated_mail(**mail_kwargs)
        else:
            send_templated_mail(**mail_kwargs)

    def generate_login_code(self):
        code = super().generate_login_code()
        if settings.DEBUG:
            logger.info(
                "\n"
                "╔══════════════════════════════════════╗\n"
                "║       LOGIN CODE: %-18s ║\n"
                "╚══════════════════════════════════════╝" % code
            )
        return code


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that permits logins only from specific domains."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.allowed_domains = (
            pj_settings().allowed_login_domains.split()
            if pj_settings().allowed_login_domains
            else None
        )

    def pre_social_login(self, request, sociallogin):
        domain = sociallogin.email_addresses[0].email.split("@", 1)[1]

        if self.allowed_domains and domain not in self.allowed_domains:
            messages.error(request, f"Domain {domain} not allowed.")
            raise ImmediateHttpResponse(redirect_to_login(next="/"))

        # find the user, connect the social account if it isn't connected, then log them in
        if sociallogin.account.extra_data.get("email", None):
            user = User.objects.filter(
                email=sociallogin.account.extra_data["email"]
            ).first()
            if user:
                social_account = SocialAccount.objects.filter(user=user).first()
                if not social_account:
                    sociallogin.state["process"] = "connect"
                    perform_login(request, user, email_verification="none")

    def is_open_for_signup(self, request, sociallogin):
        return pj_settings().allow_social_logins
