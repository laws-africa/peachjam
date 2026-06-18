import os
import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from peachjam.models import UserProfile
from peachjam.sentry import (
    SENTRY_SAMPLING_COOKIE_NAME,
    SENTRY_SAMPLING_COOKIE_SALT,
    SENTRY_SAMPLING_MAX_AGE,
    get_sentry_sampling_mode_from_request,
    get_sentry_sampling_mode_from_wsgi_environ,
    sentry_profiles_sampler,
    sentry_traces_sampler,
)


class SentrySamplingTests(TestCase):
    fixtures = ["tests/languages"]

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", is_staff=True
        )
        self.regular = User.objects.create_user(
            username="regular", email="regular@example.com"
        )
        UserProfile.objects.get_or_create(user=self.staff)
        UserProfile.objects.get_or_create(user=self.regular)

    def test_staff_can_issue_trace_cookie(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("sentry_sampling", args=["trace"]), {"next": reverse("about")}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("about"))
        cookie = response.cookies[SENTRY_SAMPLING_COOKIE_NAME]
        self.assertEqual(cookie["max-age"], SENTRY_SAMPLING_MAX_AGE)
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_profile_cookie_is_issued_for_staff(self):
        self.client.force_login(self.staff)

        self.client.get(reverse("sentry_sampling", args=["profile"]))
        request = self.client.get(reverse("loaded")).wsgi_request

        self.assertEqual(get_sentry_sampling_mode_from_request(request), "profile")

    def test_non_staff_cannot_issue_cookie(self):
        self.client.force_login(self.regular)

        response = self.client.get(reverse("sentry_sampling", args=["trace"]))

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(SENTRY_SAMPLING_COOKIE_NAME, response.cookies)

    def test_unsafe_next_url_falls_back_to_home_page(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("sentry_sampling", args=["trace"]),
            {"next": "https://example.com/not-this-site"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home_page"))

    def test_wsgi_cookie_parser_rejects_expired_cookie(self):
        with patch(
            "django.core.signing.time.time",
            return_value=time.time() - SENTRY_SAMPLING_MAX_AGE - 1,
        ):
            cookie_value = signing.dumps(
                {"mode": "trace"}, salt=SENTRY_SAMPLING_COOKIE_SALT
            )

        self.assertIsNone(
            get_sentry_sampling_mode_from_wsgi_environ(
                {"HTTP_COOKIE": f"{SENTRY_SAMPLING_COOKIE_NAME}={cookie_value}"}
            )
        )

    def test_wsgi_cookie_parser_rejects_malformed_cookie_header(self):
        self.assertIsNone(
            get_sentry_sampling_mode_from_wsgi_environ({"HTTP_COOKIE": "bad;cookie"})
        )

    def test_samplers_force_trace_and_profile_from_cookie(self):
        cookie_value = signing.dumps(
            {"mode": "profile"}, salt=SENTRY_SAMPLING_COOKIE_SALT
        )
        context = {
            "wsgi_environ": {
                "HTTP_COOKIE": f"{SENTRY_SAMPLING_COOKIE_NAME}={cookie_value}"
            }
        }

        self.assertEqual(sentry_traces_sampler(context), 1.0)
        self.assertEqual(sentry_profiles_sampler(context), 1.0)

    def test_samplers_fall_back_without_cookie(self):
        with patch.dict(os.environ, {"SENTRY_SAMPLE_RATE": "0.25"}, clear=False):
            self.assertEqual(sentry_traces_sampler({}), 0.25)

        self.assertEqual(sentry_profiles_sampler({}), 0.0)

    def test_staff_loaded_menu_includes_sampling_items(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("loaded"))

        self.assertContains(response, "Trace for 5 mins")
        self.assertContains(response, "Profile for 5 mins")

    def test_loaded_menu_marks_active_profile(self):
        self.client.force_login(self.staff)
        self.client.get(reverse("sentry_sampling", args=["profile"]))

        response = self.client.get(reverse("loaded"))

        self.assertContains(response, "Profile for 5 mins")
        self.assertContains(response, "bi-check-lg")

    def test_regular_loaded_menu_excludes_sampling_items(self):
        self.client.force_login(self.regular)

        response = self.client.get(reverse("loaded"))

        self.assertNotContains(response, "Trace for 5 mins")
        self.assertNotContains(response, "Profile for 5 mins")
