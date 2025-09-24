from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

from peachjam.models import Taxonomy

User = get_user_model()


class TaxonomyTestCase(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        root = Taxonomy.add_root(name="Collections")
        first_child = root.add_child(name="Land Rights")
        second_child = first_child.add_child(name="Environment")
        second_child.add_child(name="Climate Change")

        second_child.restricted = True
        second_child.save()

        officer_group = Group.objects.get(name="Officers")
        assign_perm("view_taxonomy", officer_group, second_child)

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
