from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from peachjam.models.flynote import Flynote, FlynoteDocumentCount


class FlynoteManagerViewTest(TestCase):
    fixtures = ["tests/languages"]

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="password",
        )
        change_flynote = Permission.objects.get(codename="change_flynote")
        self.staff_user.user_permissions.add(change_flynote)
        self.criminal = Flynote.add_root(name="Criminal law")
        self.contract = Flynote.add_root(name="Contract law", deprecated=True)
        self.criminal.refresh_from_db()
        self.sentencing = self.criminal.add_child(name="Sentencing")
        self.criminal.refresh_from_db()
        self.bail = self.criminal.add_child(name="Bail")
        self.sentencing.refresh_from_db()
        self.appeals = self.sentencing.add_child(name="Appeals")
        FlynoteDocumentCount.objects.create(flynote=self.criminal, count=3)
        FlynoteDocumentCount.objects.create(flynote=self.sentencing, count=2)
        FlynoteDocumentCount.objects.create(flynote=self.bail, count=1)

    def test_manager_requires_staff(self):
        response = self.client.get(reverse("flynote-manager"))
        self.assertNotEqual(response.status_code, 200)

        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("flynote-manager"))
        self.assertNotEqual(response.status_code, 200)

    def test_staff_can_load_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-vue-component="FlynoteManager"')
        self.assertContains(response, 'data-path-url="')

    def test_tree_endpoint_returns_root_nodes(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager-tree"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        names = {node["name"] for node in payload["results"]}
        self.assertEqual(names, {"Criminal law", "Contract law"})
        criminal = next(
            node for node in payload["results"] if node["name"] == "Criminal law"
        )
        contract = next(
            node for node in payload["results"] if node["name"] == "Contract law"
        )
        self.assertEqual(criminal["document_count"], 3)
        self.assertEqual(criminal["numchild"], 2)
        self.assertTrue(criminal["has_children"])
        self.assertTrue(contract["deprecated"])

    def test_children_endpoint_returns_direct_children_only(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-tree-children", args=[self.criminal.pk])
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        names = {node["name"] for node in payload["results"]}
        self.assertEqual(names, {"Bail", "Sentencing"})
        self.assertNotIn("Appeals", names)

    def test_path_endpoint_returns_path_to_node(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-tree-path", args=[self.appeals.pk])
        )
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.json()["path"],
            [self.criminal.pk, self.sentencing.pk, self.appeals.pk],
        )

    def test_workspace_detail_renders_node_path(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-detail", args=[self.sentencing.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Criminal law")
        self.assertContains(response, "Sentencing")
        self.assertContains(response, "2 judgments total")
        self.assertContains(response, f'href="{self.sentencing.get_absolute_url()}"')
        self.assertContains(response, "View on site")
        self.assertContains(
            response,
            f'href="{reverse("flynote-manager")}?flynote={self.criminal.pk}"',
        )
        self.assertContains(
            response,
            f'data-flynote-id="{self.sentencing.pk}"',
        )
        self.assertContains(
            response,
            f'hx-post="/en/admin/flynote-manager/workspace/{self.sentencing.pk}/"',
        )
        self.assertContains(response, "Depth")
        self.assertNotContains(response, '<dt class="col-sm-3">Children</dt>')
        self.assertContains(response, "card-footer")
        self.assertContains(response, "Danger zone")
        self.assertContains(response, "Deprecation will prevent this flynote")
        self.assertContains(response, "Deprecate")
        self.assertNotContains(response, "id_deprecated")

    def test_workspace_detail_shows_deprecated_alert(self):
        self.sentencing.deprecated = True
        self.sentencing.save()
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-detail", args=[self.sentencing.pk])
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "alert-warning")
        self.assertContains(response, "This flynote is deprecated")
        self.assertContains(response, "will not be re-used")

    def test_workspace_detail_post_updates_flynote(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"name": "Sentence review"},
        )
        self.assertEqual(response.status_code, 200)

        self.sentencing.refresh_from_db()
        self.assertEqual(self.sentencing.name, "Sentence review")
        self.assertFalse(self.sentencing.deprecated)
        self.assertContains(response, "Flynote saved.")
        self.assertIn("flynote-updated", response.headers["HX-Trigger"])

    def test_workspace_detail_requires_change_permission_to_edit(self):
        staff_without_permission = User.objects.create_user(
            username="readonly-staff@example.com",
            email="readonly-staff@example.com",
            password="password",
            is_staff=True,
        )
        self.client.force_login(staff_without_permission)

        get_response = self.client.get(
            reverse("flynote-manager-detail", args=[self.sentencing.pk])
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertNotContains(get_response, "card-footer")
        self.assertNotContains(get_response, "Danger zone")

        post_response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"name": "Sentence review"},
        )
        self.assertEqual(post_response.status_code, 403)

    def test_workspace_detail_post_deprecates_flynote(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"_action": "deprecate"},
        )
        self.assertEqual(response.status_code, 302)

        self.sentencing.refresh_from_db()
        self.assertTrue(self.sentencing.deprecated)
        self.assertEqual(
            response.url,
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
        )

    def test_workspace_detail_post_undeprecates_flynote(self):
        self.sentencing.deprecated = True
        self.sentencing.save()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"_action": "undeprecate"},
        )
        self.assertEqual(response.status_code, 302)

        self.sentencing.refresh_from_db()
        self.assertFalse(self.sentencing.deprecated)
        self.assertEqual(
            response.url,
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
        )

    def test_workspace_detail_post_renders_form_errors(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"name": "Bail"},
        )
        self.assertEqual(response.status_code, 200)

        self.sentencing.refresh_from_db()
        self.assertEqual(self.sentencing.name, "Sentencing")
        self.assertContains(response, "A sibling flynote already has this name")
        self.assertNotIn("HX-Trigger", response.headers)

    def test_workspace_search_renders_empty_shell(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager-search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search tools will appear here.")
