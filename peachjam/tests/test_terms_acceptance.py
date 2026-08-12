from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class TermsAcceptanceMiddlewareTests(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        profile = self.user.userprofile
        profile.accepted_terms_at = None
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
