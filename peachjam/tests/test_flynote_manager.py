from django.contrib.auth.models import User
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
        self.assertContains(
            response,
            f'href="{reverse("flynote-manager")}?flynote={self.criminal.pk}"',
        )
        self.assertContains(
            response,
            f'data-flynote-id="{self.sentencing.pk}"',
        )

    def test_workspace_search_renders_empty_shell(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager-search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search tools will appear here.")
