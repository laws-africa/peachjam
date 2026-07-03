from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse

from peachjam.models import pj_settings


class AccountFeatureFlagTests(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
    ]

    def test_annotation_views_return_404_when_annotations_disabled(self):
        site_settings = pj_settings()
        site_settings.allow_annotations = False
        site_settings.save()

        response = self.client.get(reverse("annotation_list", args=[4124]))

        self.assertEqual(response.status_code, 404)

    @override_settings(PEACHJAM={**settings.PEACHJAM, "DISABLE_ACCOUNTS": True})
    def test_my_home_returns_404_when_accounts_disabled(self):
        user = User.objects.first()
        self.client._login(user, "django.contrib.auth.backends.ModelBackend")

        response = self.client.get(reverse("my_home"))

        self.assertEqual(response.status_code, 404)

    @override_settings(PEACHJAM={**settings.PEACHJAM, "DISABLE_ACCOUNTS": True})
    def test_saved_search_button_returns_404_when_accounts_disabled(self):
        site_settings = pj_settings()
        site_settings.allow_save_searches = True
        site_settings.save()

        response = self.client.get(reverse("search:saved_search_button"))

        self.assertEqual(response.status_code, 404)

    def test_user_following_button_returns_empty_response_when_follows_disabled(self):
        site_settings = pj_settings()
        site_settings.allow_follows = False
        site_settings.save()

        response = self.client.get(reverse("user_following_button") + "?taxonomy=1")

        self.assertEqual(response.status_code, 204)

    def test_user_following_list_requires_view_permission(self):
        user = User.objects.first()
        self.client._login(user, "django.contrib.auth.backends.ModelBackend")

        response = self.client.get(reverse("user_following_list"))

        self.assertEqual(response.status_code, 403)

        user.user_permissions.add(Permission.objects.get(codename="view_userfollowing"))
        response = self.client.get(reverse("user_following_list"))

        self.assertEqual(response.status_code, 200)
