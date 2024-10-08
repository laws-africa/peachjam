from allauth.account.utils import perform_login
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login

from peachjam.models import pj_settings


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
        return False
