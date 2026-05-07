import datetime
import json

from countries_plus.models import Country
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import Court, Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote


class FlynoteManagerViewTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

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
        delete_flynote = Permission.objects.get(codename="delete_flynote")
        self.staff_user.user_permissions.add(change_flynote, delete_flynote)
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

    def make_judgment(self):
        return Judgment.objects.create(
            case_name="Linked judgment",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

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

    def test_admin_changelist_points_to_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("admin:peachjam_flynote_changelist"))
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Flynotes are managed in the flynote manager.")
        self.assertContains(response, f'href="{reverse("flynote-manager")}"')

    def test_admin_change_view_redirects_to_manager_detail(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("admin:peachjam_flynote_change", args=[self.sentencing.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("flynote-manager")}?flynote={self.sentencing.pk}',
        )

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
        self.assertContains(response, "Merge")
        self.assertContains(response, "Deprecation will prevent this flynote")
        self.assertContains(
            response, "Deleting this flynote will also delete all descendant topics"
        )
        self.assertContains(response, "Only topics with no linked judgments can be")
        self.assertContains(response, "Deprecate")
        self.assertContains(response, "Delete")
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
        self.assertNotContains(get_response, "Merge")

        post_response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"name": "Sentence review"},
        )
        self.assertEqual(post_response.status_code, 403)

        merge_response = self.client.get(
            reverse("flynote-manager-merge", args=[self.sentencing.pk])
        )
        self.assertEqual(merge_response.status_code, 403)

    def test_workspace_detail_requires_delete_permission_to_delete(self):
        staff_without_permission = User.objects.create_user(
            username="change-only-staff@example.com",
            email="change-only-staff@example.com",
            password="password",
            is_staff=True,
        )
        staff_without_permission.user_permissions.add(
            Permission.objects.get(codename="change_flynote")
        )
        self.client.force_login(staff_without_permission)

        post_response = self.client.post(
            reverse("flynote-manager-detail", args=[self.appeals.pk]),
            {"_action": "delete"},
        )
        self.assertEqual(post_response.status_code, 403)

    def test_workspace_detail_delete_deletes_descendants_and_redirects_to_parent(self):
        child_pk = self.appeals.pk
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"_action": "delete"},
        )
        self.assertEqual(response.status_code, 204)

        self.assertFalse(Flynote.objects.filter(pk=self.sentencing.pk).exists())
        self.assertFalse(Flynote.objects.filter(pk=child_pk).exists())
        self.assertEqual(
            response.headers["HX-Redirect"],
            f'{reverse("flynote-manager")}?flynote={self.criminal.pk}',
        )

    def test_workspace_detail_delete_root_redirects_to_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.contract.pk]),
            {"_action": "delete"},
        )
        self.assertEqual(response.status_code, 204)

        self.assertFalse(Flynote.objects.filter(pk=self.contract.pk).exists())
        self.assertEqual(response.headers["HX-Redirect"], reverse("flynote-manager"))

    def test_workspace_detail_delete_renders_linked_judgment_error(self):
        JudgmentFlynote.objects.create(
            document=self.make_judgment(),
            flynote=self.appeals,
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-detail", args=[self.sentencing.pk]),
            {"_action": "delete"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(Flynote.objects.filter(pk=self.sentencing.pk).exists())
        self.assertContains(response, "cannot be deleted")
        self.assertContains(response, "has linked judgments")
        self.assertNotContains(response, "This field is required")

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

    def test_duplicate_name_error_links_to_manager_merge_tab(self):
        self.sentencing.name = "Bail"

        with self.assertRaises(ValidationError) as raised:
            self.sentencing.full_clean()

        error = str(raised.exception.message_dict["name"][0])
        self.assertIn(
            (
                f'{reverse("flynote-manager")}?flynote={self.bail.pk}&amp;tab=merge'
                f"&amp;selected={self.sentencing.pk}"
            ),
            error,
        )
        self.assertIn("Merge this flynote into that one", error)

    def test_workspace_search_renders_empty_shell(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager-search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search flynotes")
        self.assertContains(
            response, "Enter a flynote name or choose a depth to search."
        )
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'name="depth"')
        self.assertContains(response, "Any depth")

    def test_workspace_search_returns_matching_flynotes(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("flynote-manager-search"), {"q": "sent"})
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Sentencing")
        self.assertContains(response, "Criminal law — Sentencing")
        self.assertContains(
            response,
            f'href="{reverse("flynote-manager")}?flynote={self.sentencing.pk}"',
        )
        self.assertContains(response, f'data-flynote-id="{self.sentencing.pk}"')
        self.assertContains(response, "<td>2</td>", html=True)
        self.assertContains(response, "<td>1</td>", html=True)
        self.assertNotContains(response, "Bail")

    def test_workspace_search_only_matches_flynote_name_and_marks_deprecated(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-search"),
            {"q": "law"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Criminal law")
        self.assertContains(response, "Contract law")
        self.assertContains(response, "Deprecated")
        self.assertNotContains(response, "Sentencing")

    def test_workspace_search_filters_by_depth(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-search"),
            {"q": "law", "depth": "1"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Criminal law")
        self.assertContains(response, "Contract law")
        self.assertNotContains(response, "Sentencing")
        self.assertContains(
            response, '<option value="1" selected>1</option>', html=True
        )

        response = self.client.get(
            reverse("flynote-manager-search"),
            {"q": "law", "depth": "2"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matching flynotes found.")
        self.assertNotContains(response, "Criminal law")

    def test_workspace_search_allows_depth_without_query(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-search"),
            {"depth": "2"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Bail")
        self.assertContains(response, "Sentencing")
        self.assertNotContains(
            response,
            f'href="{reverse("flynote-manager")}?flynote={self.criminal.pk}"',
        )

    def test_workspace_merge_loads_sibling_candidates(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-merge", args=[self.sentencing.pk]),
            {"q": ""},
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Bail")
        self.assertContains(
            response,
            f'href="{reverse("flynote-manager")}?flynote={self.bail.pk}"',
        )
        self.assertContains(response, 'target="_blank"')
        self.assertNotContains(response, "Appeals")

    def test_workspace_merge_defaults_search_to_target_name(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-merge", args=[self.sentencing.pk])
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            '<input id="id_q" type="search" name="q" value="Sentencing" class="form-control"/>',
            html=True,
        )

    def test_workspace_detail_can_deep_link_to_merge_tab(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("flynote-manager-detail", args=[self.bail.pk]),
            {"tab": "merge", "selected": self.sentencing.pk},
        )
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, 'id="flynote-manager-merge-tab"')
        self.assertContains(response, 'aria-selected="true"')
        self.assertContains(
            response,
            '<input id="id_q" type="search" name="q" value="Bail" class="form-control"/>',
            html=True,
        )
        self.assertContains(
            response,
            f'<input type="hidden" name="selected" value="{self.sentencing.pk}"/>',
            html=True,
        )

    def test_workspace_merge_picker_adds_and_removes_selected_flynotes(self):
        self.client.force_login(self.staff_user)
        add_response = self.client.get(
            reverse("flynote-manager-merge-picker", args=[self.sentencing.pk]),
            {"q": "", "add": self.bail.pk},
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertContains(
            add_response,
            f'<input type="hidden" name="selected" value="{self.bail.pk}"/>',
            html=True,
        )
        self.assertContains(add_response, "Remove")

        remove_response = self.client.get(
            reverse("flynote-manager-merge-picker", args=[self.sentencing.pk]),
            {"q": "", "selected": self.bail.pk, "remove": self.bail.pk},
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertContains(remove_response, "No flynotes selected yet.")

    def test_workspace_merge_merges_child_sibling_and_rerenders_merge_tab(self):
        JudgmentFlynote.objects.create(
            document=self.make_judgment(),
            flynote=self.sentencing,
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-merge", args=[self.sentencing.pk]),
            {"q": "", "selected": self.bail.pk},
        )
        self.assertEqual(response.status_code, 200)

        self.assertFalse(Flynote.objects.filter(pk=self.bail.pk).exists())
        self.assertContains(response, "Merged 1 flynotes into Sentencing.")
        self.assertContains(response, 'id="flynote-manager-merge-tab"')
        self.assertContains(response, 'aria-selected="true"')
        trigger = json.loads(response.headers["HX-Trigger"])
        self.assertEqual(
            trigger["flynote-merged"],
            {"targetId": self.sentencing.pk, "parentId": self.criminal.pk},
        )

    def test_workspace_merge_merges_root_sibling_and_reloads_roots(self):
        JudgmentFlynote.objects.create(
            document=self.make_judgment(),
            flynote=self.criminal,
        )
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-merge", args=[self.criminal.pk]),
            {"q": "", "selected": self.contract.pk},
        )
        self.assertEqual(response.status_code, 200)

        self.assertFalse(Flynote.objects.filter(pk=self.contract.pk).exists())
        trigger = json.loads(response.headers["HX-Trigger"])
        self.assertEqual(
            trigger["flynote-merged"],
            {"targetId": self.criminal.pk, "parentId": None},
        )

    def test_workspace_merge_renders_validation_error(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("flynote-manager-merge", args=[self.bail.pk]),
            {"q": "", "selected": self.appeals.pk},
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(Flynote.objects.filter(pk=self.appeals.pk).exists())
        self.assertContains(
            response,
            "Flynotes can only be merged into a sibling at the same level.",
        )
        self.assertContains(response, 'id="flynote-manager-merge-tab"')
        self.assertNotIn("HX-Trigger", response.headers)
