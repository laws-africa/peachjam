from allauth.account.utils import perform_login
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that permits logins only from specific domains."""

    ALLOWED_DOMAINS = ["laws.africa", "africanlii.org"]

    def pre_social_login(self, request, sociallogin):
        domain = sociallogin.email_addresses[0].email.split("@", 1)[1]

        if domain not in self.ALLOWED_DOMAINS:
            messages.error(request, f"Domain {domain} not allowed.")
            raise ImmediateHttpResponse(redirect_to_login(next="/"))

        # find the user, connect the social account if it isn't connected, then log them in
        if sociallogin.account.extra_data.get("email", None):
            user = User.objects.filter(email=sociallogin.account.extra_data["email"]).first()
            if user:
                social_account = SocialAccount.objects.filter(user=user).first()
                if not social_account:
                    sociallogin.state["process"] = "connect"
                    perform_login(request, user, email_verification="none")
