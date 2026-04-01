from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls.base import reverse
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

from peachjam.models import Taxonomy

User = get_user_model()


class TaxonomyTestCase(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.root = Taxonomy.add_root(name="Collections")
        first_child = self.root.add_child(name="Land Rights")
        second_child = first_child.add_child(name="Environment")
        second_child.add_child(name="Climate Change")

        second_child.restricted = True
        second_child.save()

        officer_group = Group.objects.get(name="Officers")
        assign_perm("view_taxonomy", officer_group, second_child)

    def test_taxonomy_listing(self):
        response = self.app.get(reverse("top_level_taxonomy_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("public", response.headers.get("Cache-Control", ""))

        response = self.app.get(self.root.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("public", response.headers.get("Cache-Control", ""))

    def test_restricted_taxonomy_unauthorized(self):
        unauthorized_user = User.objects.get(username="user@example.com")
        land = Taxonomy.objects.get(name="Land Rights")
        response = self.app.get(land.get_absolute_url(), user=unauthorized_user)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Climate Change", response.text)

        environment = Taxonomy.objects.get(name="Environment")
        response = self.app.get(
            environment.get_absolute_url(), user=unauthorized_user, expect_errors=True
        )
        self.assertEqual(response.status_code, 403)

    def test_restricted_taxonomy_authorized(self):
        authorized_user = User.objects.get(username="officer@example.com")
        land = Taxonomy.objects.get(name="Land Rights")
        response = self.app.get(land.get_absolute_url(), user=authorized_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Climate Change", response.text)

        environment = Taxonomy.objects.get(name="Environment")
        response = self.app.get(environment.get_absolute_url(), user=authorized_user)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("public", response.headers.get("Cache-Control", ""))

    def test_first_level_taxonomy_page_does_not_need_get_root_for_child_links(self):
        with patch.object(
            Taxonomy,
            "get_root",
            side_effect=AssertionError("get_root should not be called for child links"),
        ):
            response = self.app.get(
                reverse("first_level_taxonomy_list", kwargs={"topic": self.root.slug})
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/taxonomy/collections/collections-land-rights", response.text)

    def test_taxonomy_detail_page_does_not_need_get_root_for_breadcrumb_links(self):
        environment = Taxonomy.objects.get(name="Environment")
        with patch.object(
            Taxonomy,
            "get_root",
            side_effect=AssertionError(
                "get_root should not be called for taxonomy detail breadcrumbs"
            ),
        ):
            response = self.app.get(
                reverse(
                    "taxonomy_detail",
                    kwargs={"topic": self.root.slug, "child": environment.slug},
                ),
                user=User.objects.get(username="officer@example.com"),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("/taxonomy/collections", response.text)
        self.assertIn("/taxonomy/collections/collections-land-rights", response.text)

    def test_taxonomy_detail_404s_for_mismatched_root_and_child(self):
        other_root = Taxonomy.add_root(name="Other collections")
        environment = Taxonomy.objects.get(name="Environment")

        response = self.app.get(
            reverse(
                "taxonomy_detail",
                kwargs={"topic": other_root.slug, "child": environment.slug},
            ),
            expect_errors=True,
        )

        self.assertEqual(response.status_code, 404)
