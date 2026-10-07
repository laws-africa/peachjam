from allauth.account.views import logout as account_logout
from allauth.socialaccount.providers.google.views import oauth2_callback, oauth2_login
from django.conf import settings
from django.http import Http404
from django.urls import include, path
from django.views import View
from django.views.generic import RedirectView

from peachjam.views import (
    AcceptTermsView,
    AccountView,
    DeleteAccountView,
    DocumentAccessGroupDetailView,
    EditAccountView,
    LoggedOutView,
)
from peachjam.views.accounts import OnboardView, SignupView, UserAuthView


class DisabledAccountUrlsView(View):
    def dispatch(self, request, *args, **kwargs):
        raise Http404


urlpatterns = []

if settings.PEACHJAM["DISABLE_ACCOUNTS"]:
    # Keep the normal account URL patterns registered below so reverse() still
    # works, but prepend catch-all routes so incoming account requests resolve
    # to 404 while accounts are disabled. The Google login flow and logout
    # routes remain available so staff can sign in to and out of the Django
    # admin.
    urlpatterns += [
        path("google/login/", oauth2_login, name="google_login"),
        # Google OAuth redirect URIs are sometimes configured without a trailing
        # slash. Allow that exact callback too because the catch-all below would
        # otherwise prevent Django's APPEND_SLASH redirect.
        path("google/login/callback", oauth2_callback),
        path("google/login/callback/", oauth2_callback, name="google_callback"),
        path("logout/", account_logout, name="account_logout"),
        path("logged-out", LoggedOutView.as_view(), name="account_logged_out"),
        path("", DisabledAccountUrlsView.as_view()),
        path("<path:path>", DisabledAccountUrlsView.as_view()),
    ]

urlpatterns += [
    path("signup/", SignupView.as_view(), name="account_signup"),
    path("", include("allauth.urls")),
    path("accept-terms/", AcceptTermsView.as_view(), name="account_accept_terms"),
    path(
        "onboard",
        OnboardView.as_view(),
        name="account_onboard",
    ),
    path("profile/", AccountView.as_view(), name="my_account"),
    path("profile/edit", EditAccountView.as_view(), name="edit_account"),
    path("offboarding", DeleteAccountView.as_view(), name="delete_account"),
    path("logged-out", LoggedOutView.as_view(), name="account_logged_out"),
    path(
        "document-access-groups/",
        include(
            [
                path(
                    "<int:pk>",
                    DocumentAccessGroupDetailView.as_view(),
                    name="document_access_group_detail",
                ),
            ]
        ),
    ),
]

# OTP-specific URLs: redirect allauth's "request a code" page to login,
# and register our custom verification view.
if settings.PEACHJAM["AUTH_OTP"]:
    urlpatterns += [
        path(
            "login/code/",
            RedirectView.as_view(pattern_name="account_login", query_string=True),
            name="account_request_login_code",
        ),
        path("login/auth", UserAuthView.as_view(), name="account_confirm_login_code"),
    ]
