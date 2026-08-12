from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone


class TermsAcceptanceMiddlewareTests(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        profile = self.user.userprofile
        profile.accepted_terms_at = None
        profile.onboarding_completed_at = timezone.now()
        profile.save()

    def _login(self):
        self.client.force_login(self.user)

    def test_redirects_to_accept_terms_when_not_accepted(self):
        self._login()
        # home page is allowed
        response = self.client.get(reverse("home_page"))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 302)

        redirect_bits = urlparse(response["Location"])
        self.assertEqual(redirect_bits.path, reverse("account_accept_terms"))
        self.assertEqual(
            parse_qs(redirect_bits.query).get("next"),
            [reverse("about")],
        )

    def test_accepting_terms_updates_profile_and_redirects(self):
        self._login()
        next_url = reverse("home_page")

        response = self.client.post(
            reverse("account_accept_terms"),
            data={"accepted_terms": True, "next": next_url},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.userprofile.accepted_terms_at)

    def test_access_granted_after_acceptance(self):
        self._login()

        self.client.post(
            reverse("account_accept_terms"),
            data={"accepted_terms": True},
        )

        response = self.client.get(reverse("home_page"))
        self.assertEqual(response.status_code, 200)

    def test_terms_pages_remain_accessible(self):
        self._login()

        self.assertEqual(
            self.client.get(reverse("account_accept_terms")).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("terms_of_use")).status_code,
            200,
        )


class OnboardingMiddlewareTests(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.profile = self.user.userprofile
        self.profile.accepted_terms_at = timezone.now()
        self.profile.onboarding_completed_at = None
        self.profile.onboarding_skipped_at = None
        self.profile.save()

    def _login(self):
        self.client.force_login(self.user)

    def test_redirects_incomplete_users_to_onboarding(self):
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 302)
        redirect_bits = urlparse(response["Location"])
        self.assertEqual(redirect_bits.path, reverse("account_onboard"))
        self.assertEqual(parse_qs(redirect_bits.query).get("next"), [reverse("about")])

    def test_completed_users_are_not_redirected(self):
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.save()
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)

    def test_skipped_users_are_not_redirected(self):
        self.profile.onboarding_skipped_at = timezone.now()
        self.profile.save()
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)

    def test_skipped_users_are_redirected_after_cooldown(self):
        self.profile.onboarding_skipped_at = timezone.now() - timedelta(days=8)
        self.profile.save()
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            urlparse(response["Location"]).path, reverse("account_onboard")
        )

    def test_completed_users_are_not_redirected_after_skip_timestamp(self):
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.onboarding_skipped_at = timezone.now()
        self.profile.save()
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)

    def test_social_account_users_are_sent_to_onboarding(self):
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="google-uid",
        )
        self._login()

        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            urlparse(response["Location"]).path, reverse("account_onboard")
        )
