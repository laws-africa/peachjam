from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from peachjam.models import Court, UserFollowing, pj_settings
from peachjam.tests import test_saved_documents
from peachjam.views.chat import StartDocumentChatView
from peachjam.views.save_document import FolderCreateView, SavedDocumentCreateView
from peachjam.views.user_following import (
    UserFollowingButtonView,
    UserFollowingCreateView,
)
from peachjam_search.models import SavedSearch
from peachjam_search.views.search import SavedSearchCreateView


class OperationPermissionContextTests(TestCase):
    fixtures = test_saved_documents.SavedDocumentViewsTest.fixtures
    setUp = test_saved_documents.SavedDocumentViewsTest.setUp

    def grant_list_permissions(self):
        self.user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_folder",
                    "view_savedsearch",
                    "change_savedsearch",
                    "view_userfollowing",
                    "delete_userfollowing",
                ]
            )
        )
        settings = pj_settings()
        settings.allow_follows = True
        settings.allow_save_searches = True
        settings.save()

    def seen(self, hook):
        return {call.kwargs.get("permission") for call in hook.call_args_list}

    def test_folder_list_passes_distinct_target_permissions_to_its_includes(self):
        self.grant_list_permissions()
        with (
            patch.object(
                FolderCreateView, "permission_required", "example.create_folder"
            ),
            patch.object(
                SavedDocumentCreateView, "permission_required", "example.save_document"
            ),
            patch(
                "peachjam.auth.AccountAdapter.get_account_url", return_value="/account/"
            ) as hook,
        ):
            response = self.client.get(reverse("folder_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["create_folder_permission"], "example.create_folder"
        )
        self.assertEqual(
            response.context["save_document_permission"], "example.save_document"
        )
        self.assertTrue(
            {"example.create_folder", "example.save_document"}.issubset(self.seen(hook))
        )

    def test_saved_document_edit_and_fragments_use_create_operation_permission(self):
        for url, data in [
            (reverse("saved_document_modal", args=[self.doc1.pk]), {"doc_id": 5389}),
            (reverse("saved_document_fragments"), {"doc_ids": "5389"}),
        ]:
            with (
                self.subTest(url=url),
                patch.object(
                    SavedDocumentCreateView,
                    "permission_required",
                    "example.save_document",
                ),
                patch(
                    "peachjam.auth.AccountAdapter.get_account_url",
                    return_value="/account/",
                ) as hook,
            ):
                response = self.client.get(url, data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["save_document_permission"],
                    "example.save_document",
                )
                self.assertIn("example.save_document", self.seen(hook))

    def test_anonymous_saved_document_prompt_uses_its_view_permission(self):
        self.client.logout()
        with (
            patch.object(
                SavedDocumentCreateView, "permission_required", "example.save_document"
            ),
            patch(
                "peachjam.auth.AccountAdapter.get_account_url", return_value="/account/"
            ) as hook,
        ):
            response = self.client.post(
                reverse("saved_document_create") + "?doc_id=5389",
                HTTP_HX_CURRENT_URL="http://testserver/document",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["required_permission"], "example.save_document"
        )
        self.assertIn("example.save_document", self.seen(hook))

    def test_saved_search_button_list_and_edit_use_create_view_permission(self):
        self.grant_list_permissions()
        saved = SavedSearch.objects.create(user=self.user, q="example")
        for url in [
            reverse("search:saved_search_button"),
            reverse("search:saved_search_list"),
            reverse("search:saved_search_update", args=[saved.pk]),
        ]:
            with (
                self.subTest(url=url),
                patch.object(
                    SavedSearchCreateView,
                    "permission_required",
                    "example.create_search",
                ),
                patch(
                    "peachjam.auth.AccountAdapter.get_account_url",
                    return_value="/account/",
                ) as hook,
            ):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["create_saved_search_permission"],
                    "example.create_search",
                )
                self.assertIn("example.create_search", self.seen(hook))

    def test_follow_list_and_delete_use_creation_permission(self):
        self.grant_list_permissions()
        follow = UserFollowing.objects.create(
            user=self.user, court=Court.objects.first()
        )
        for url in [
            reverse("user_following_list"),
            reverse("user_following_delete", args=[follow.pk]),
        ]:
            with (
                self.subTest(url=url),
                patch.object(
                    UserFollowingCreateView,
                    "permission_required",
                    "example.create_follow",
                ),
                patch(
                    "peachjam.auth.AccountAdapter.get_account_url",
                    return_value="/account/",
                ) as hook,
            ):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.context["create_follow_permission"],
                    "example.create_follow",
                )
                self.assertIn("example.create_follow", self.seen(hook))

    def test_anonymous_follow_button_uses_its_own_permission(self):
        self.client.logout()
        with (
            patch.object(
                UserFollowingButtonView, "permission_required", "example.follow_button"
            ),
            patch(
                "peachjam.auth.AccountAdapter.get_account_url", return_value="/account/"
            ) as hook,
        ):
            response = self.client.get(
                reverse("user_following_button"), {"court": Court.objects.first().pk}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["required_permission"], "example.follow_button"
        )
        self.assertIn("example.follow_button", self.seen(hook))

    def test_chat_usage_fragment_receives_checked_permission(self):
        request = RequestFactory().get("/")
        request.user = self.user
        view = StartDocumentChatView()
        view.setup(request)
        subscription = SimpleNamespace(
            product_offering=SimpleNamespace(
                product=SimpleNamespace(document_chat_limit=2)
            )
        )
        with (
            patch.object(StartDocumentChatView, "permission_required", "example.chat"),
            patch(
                "peachjam.views.chat.Subscription.get_or_create_active_for_user",
                return_value=subscription,
            ),
            patch(
                "peachjam.views.chat.DocumentChatThread.count_active_for_user",
                return_value=2,
            ),
            patch("peachjam.views.chat.Product.get_user_upgrade_products") as products,
            patch(
                "peachjam.views.chat.render_to_string", wraps=render_to_string
            ) as render,
            patch(
                "peachjam.auth.AccountAdapter.get_account_url", return_value="/account/"
            ) as hook,
        ):
            products.return_value.first.return_value = SimpleNamespace(name="Upgrade")
            self.assertIsNotNone(view.build_usage_limit_html())
        self.assertEqual(
            render.call_args.args[1]["required_permission"], "example.chat"
        )
        self.assertIn("example.chat", self.seen(hook))
