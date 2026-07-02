from importlib import reload
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.models import Login
from allauth.account.stages import LoginByCodeStage
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, reverse

from peachjam.auth import (
    _patched_finish,
    _patched_send_by_email,
    get_or_create_all_users_permission_group,
)


class PatchedFinishTests(TestCase):
    fixtures = ["tests/languages"]

    def _make_process(self, state=None, user=None):
        proc = MagicMock(spec=LoginCodeVerificationProcess)
        proc.state = state or {}
        proc.user = user
        proc._user = user
        return proc

    def test_creates_user_for_new_email(self):
        proc = self._make_process(state={"email": "newuser@example.com"})
        proc.user = None

        with patch("peachjam.auth._original_finish") as mock_finish:
            mock_finish.return_value = "redirect"
            result = _patched_finish(proc, "/")

        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.username, "newuser@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(proc.state["user_id"], str(user.pk))
        self.assertEqual(proc._user, user)
        mock_finish.assert_called_once_with(proc, "/")
        self.assertEqual(result, "redirect")

    def test_existing_user_not_duplicated(self):
        existing = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="somepass",
        )
        proc = self._make_process(state={"email": "existing@example.com"})
        proc.user = None

        with patch("peachjam.auth._original_finish") as mock_finish:
            mock_finish.return_value = "redirect"
            _patched_finish(proc, "/")

        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)
        self.assertEqual(proc._user, existing)
        existing.refresh_from_db()
        self.assertTrue(existing.has_usable_password())

    def test_no_email_in_state(self):
        proc = self._make_process(state={})
        proc.user = None

        with patch("peachjam.auth._original_finish") as mock_finish:
            mock_finish.return_value = "redirect"
            _patched_finish(proc, "/")

        mock_finish.assert_called_once_with(proc, "/")

    def test_user_already_set_skips_creation(self):
        """If the process already has a user, no new user should be created."""
        existing = User.objects.create_user(
            username="withuser@example.com",
            email="withuser@example.com",
        )
        proc = self._make_process(
            state={"email": "withuser@example.com"}, user=existing
        )

        with patch("peachjam.auth._original_finish") as mock_finish:
            mock_finish.return_value = "redirect"
            _patched_finish(proc, "/done")

        self.assertEqual(User.objects.filter(email="withuser@example.com").count(), 1)
        mock_finish.assert_called_once_with(proc, "/done")


@override_settings(
    AUTHENTICATION_BACKENDS=["peachjam.auth.AllUsersPermissionBackend"],
    PEACHJAM={**settings.PEACHJAM, "ALL_USERS_PERMISSION_GROUP": "All users"},
)
class AllUsersPermissionBackendTests(TestCase):
    fixtures = ["tests/languages"]

    def setUp(self):
        content_type = ContentType.objects.get_for_model(User)
        self.permission = Permission.objects.create(
            content_type=content_type,
            codename="can_use_baseline_feature",
            name="Can use baseline feature",
        )
        self.group = get_or_create_all_users_permission_group()
        self.group.permissions.add(self.permission)

    def test_group_is_created_if_missing(self):
        Group.objects.filter(name="All users").delete()

        group = get_or_create_all_users_permission_group()

        self.assertIsNotNone(group)
        self.assertEqual("All users", group.name)

    def test_anonymous_user_gets_all_users_permissions(self):
        user = AnonymousUser()

        self.assertTrue(user.has_perm("auth.can_use_baseline_feature"))

    def test_authenticated_user_gets_all_users_permissions(self):
        user = User.objects.create_user(username="test-user")

        self.assertTrue(user.has_perm("auth.can_use_baseline_feature"))

    def test_inactive_user_gets_all_users_permissions(self):
        user = User.objects.create_user(username="inactive-user", is_active=False)

        self.assertTrue(user.has_perm("auth.can_use_baseline_feature"))

    def test_permission_required_mixin_allows_anonymous_user(self):
        class TestPermissionRequiredMixin(PermissionRequiredMixin):
            permission_required = "auth.can_use_baseline_feature"

        view = TestPermissionRequiredMixin()
        view.request = RequestFactory().get("/")
        view.request.user = AnonymousUser()

        self.assertTrue(view.has_permission())

    def test_all_users_permissions_are_not_object_permissions(self):
        user = AnonymousUser()
        obj = User(username="target")

        self.assertFalse(user.has_perm("auth.can_use_baseline_feature", obj))

    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "ALL_USERS_PERMISSION_GROUP": None}
    )
    def test_setting_can_disable_all_users_permissions(self):
        user = AnonymousUser()

        self.assertFalse(user.has_perm("auth.can_use_baseline_feature"))


class PatchedSendByEmailTests(TestCase):
    def test_sends_email_and_stores_code(self):
        proc = MagicMock(spec=LoginCodeVerificationProcess)
        proc.state = {}
        proc.request = RequestFactory().get("/")

        with patch("peachjam.auth.get_adapter") as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.generate_login_code.return_value = "123456"
            mock_get_adapter.return_value = mock_adapter

            _patched_send_by_email(proc, "test@example.com")

        mock_adapter.send_mail.assert_called_once()
        call_args = mock_adapter.send_mail.call_args
        self.assertEqual(call_args[0][0], "account/email/login_code")
        self.assertEqual(call_args[0][1], "test@example.com")
        self.assertEqual(call_args[0][2]["code"], "123456")
        self.assertEqual(proc.state["code"], "123456")
        proc.add_sent_message.assert_called_once_with(
            {"email": "test@example.com", "recipient": "test@example.com"}
        )

    def test_code_stored_in_process_state(self):
        proc = MagicMock(spec=LoginCodeVerificationProcess)
        proc.state = {}
        proc.request = RequestFactory().get("/")

        with patch("peachjam.auth.get_adapter") as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.generate_login_code.return_value = "999888"
            mock_get_adapter.return_value = mock_adapter

            _patched_send_by_email(proc, "another@example.com")

        self.assertEqual(proc.state["code"], "999888")

    def test_request_passed_in_context(self):
        proc = MagicMock(spec=LoginCodeVerificationProcess)
        proc.state = {}
        proc.request = RequestFactory().get("/login/")

        with patch("peachjam.auth.get_adapter") as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.generate_login_code.return_value = "111222"
            mock_get_adapter.return_value = mock_adapter

            _patched_send_by_email(proc, "ctx@example.com")

        context = mock_adapter.send_mail.call_args[0][2]
        self.assertIs(context["request"], proc.request)

    def test_accepts_new_allauth_keyword_arguments(self):
        proc = MagicMock(spec=LoginCodeVerificationProcess)
        proc.state = {}
        proc.request = RequestFactory().get("/login/")

        with patch("peachjam.auth.get_adapter") as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.generate_login_code.return_value = "333444"
            mock_get_adapter.return_value = mock_adapter

            _patched_send_by_email(
                proc,
                "kwarg@example.com",
                skip_enumeration_mails=True,
            )

        self.assertEqual(proc.state["code"], "333444")
        mock_adapter.send_mail.assert_called_once()


class CompleteProfileViewTests(TestCase):

    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save()

    def _login(self):
        self.client.force_login(self.user)

    def test_redirects_unauthenticated(self):
        response = self.client.get(reverse("account_onboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts", response["Location"])

    def test_shows_form_when_no_first_name(self):
        self._login()
        response = self.client.get(reverse("account_onboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "first_name")

    def test_redirects_when_first_name_already_set(self):
        self.user.first_name = "Jane"
        self.user.save()
        self._login()
        response = self.client.get(reverse("account_onboard"))
        self.assertEqual(response.status_code, 302)

    def test_submit_saves_name(self):
        self._login()
        response = self.client.post(
            reverse("account_onboard"),
            data={"first_name": "Jane", "last_name": "Doe"},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertEqual(self.user.last_name, "Doe")

    def test_submit_preserves_next_url(self):
        self._login()
        next_url = reverse("home_page")
        response = self.client.post(
            reverse("account_onboard") + f"?next={next_url}",
            data={"first_name": "Jane", "last_name": "Doe", "next": next_url},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_submit_requires_first_name(self):
        self._login()
        response = self.client.post(
            reverse("account_onboard"),
            data={"first_name": "", "last_name": "Doe"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)


class UserAuthViewTests(TestCase):

    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def _make_request(self, method="get", data=None):
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.messages.storage.fallback import FallbackStorage

        factory = RequestFactory()
        if method == "post":
            request = factory.post(
                reverse("account_confirm_login_code"), data=data or {}
            )
        else:
            request = factory.get(reverse("account_confirm_login_code"))

        request.session = {}
        setattr(request, "_messages", FallbackStorage(request))
        request.user = AnonymousUser()
        return request

    def _setup_view(self, request, email, user=None):
        from allauth.account.stages import LoginStageController

        from peachjam.views.accounts import UserAuthView

        login = Login(user=user, email=email)
        stage_data = LoginCodeVerificationProcess.initial_state(user=user, email=email)
        stage_data["initiated_by_user"] = True
        stage_data["code"] = "123456"
        stage_data["sent_messages"] = [{"email": email, "recipient": email}]
        login.state["stages"] = {
            "current": LoginByCodeStage.key,
            LoginByCodeStage.key: {"data": stage_data},
        }

        ctrl = LoginStageController(request, login)
        stage = LoginByCodeStage(ctrl, request, login)

        view = UserAuthView()
        view.request = request
        view.kwargs = {}
        view.stage = stage
        view._process = LoginCodeVerificationProcess.resume(stage)
        return view

    def test_get_returns_200_with_active_session(self):
        request = self._make_request()
        view = self._setup_view(request, "test@example.com")
        response = view.get(request)
        self.assertEqual(response.status_code, 200)

    def test_context_for_new_user(self):
        request = self._make_request()
        view = self._setup_view(request, "brand_new@example.com")
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        ctx = response.context_data
        self.assertFalse(ctx.get("is_existing_user"))
        self.assertIn("signup_form", ctx)

    def test_context_for_existing_user_with_password(self):
        user = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="Str0ng!Pass",
        )
        request = self._make_request()
        view = self._setup_view(request, "existing@example.com", user=user)
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        ctx = response.context_data
        self.assertTrue(ctx.get("is_existing_user"))
        self.assertTrue(ctx.get("has_usable_password"))
        self.assertIn("password_form", ctx)

    def test_context_for_existing_user_without_password(self):
        user = User.objects.create_user(
            username="nopass@example.com",
            email="nopass@example.com",
        )
        user.set_unusable_password()
        user.save()
        request = self._make_request()
        view = self._setup_view(request, "nopass@example.com", user=user)
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        ctx = response.context_data
        self.assertTrue(ctx.get("is_existing_user"))
        self.assertFalse(ctx.get("has_usable_password"))
        self.assertNotIn("password_form", ctx)

    def test_resend_action_redirects(self):
        request = self._make_request("post", {"action": "resend"})
        view = self._setup_view(request, "test@example.com")
        response = view.post(request)
        self.assertEqual(response.status_code, 302)

    def test_password_login_no_user_redirects(self):
        request = self._make_request(
            "post", {"action": "password_login", "password": "x"}
        )
        view = self._setup_view(request, "nobody@example.com")
        response = view.post(request)
        self.assertEqual(response.status_code, 302)

    def test_signup_password_existing_user_redirects(self):
        user = User.objects.create_user(
            username="taken@example.com",
            email="taken@example.com",
        )
        request = self._make_request("post", {"action": "signup_password"})
        view = self._setup_view(request, "taken@example.com", user=user)
        response = view.post(request)
        self.assertEqual(response.status_code, 302)


class PeachjamConfirmLoginCodeFormTests(TestCase):
    def test_code_allows_non_ascii_separators(self):
        from peachjam.views.accounts import PeachjamConfirmLoginCodeForm

        form = PeachjamConfirmLoginCodeForm(
            data={"code": "qglcーbctd"},
            code="qglcbctd",
        )

        self.assertTrue(form.is_valid())

    def test_code_rejects_non_ascii_lookalikes(self):
        from peachjam.views.accounts import PeachjamConfirmLoginCodeForm

        form = PeachjamConfirmLoginCodeForm(
            data={"code": "аbc123"},
            code="abc123",
        )

        self.assertFalse(form.is_valid())


class HeaderUserMenuTests(TestCase):
    fixtures = ["tests/languages", "tests/users"]

    def render_menu(self, disable_accounts=False):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.htmx = SimpleNamespace(current_url_abs_path="/")
        context = {
            "request": request,
            "user": request.user,
            "PEACHJAM_SETTINGS": SimpleNamespace(),
            "DISABLE_ACCOUNTS": disable_accounts,
        }
        return render_to_string("peachjam/user/_menu.html", context, request=request)

    def test_header_shows_login_button_when_account_urls_enabled(self):
        html = self.render_menu(disable_accounts=False)

        self.assertIn(f'href="{reverse("account_login")}?next=/"', html)

    def test_header_hides_login_button_when_account_urls_disabled(self):
        html = self.render_menu(disable_accounts=True)

        self.assertNotIn(f'href="{reverse("account_login")}?next=/"', html)

    def test_authenticated_header_hides_frontend_account_links_when_accounts_disabled(
        self,
    ):
        request = RequestFactory().get("/")
        request.user = User.objects.first()
        request.user.is_staff = True
        request.htmx = SimpleNamespace(current_url_abs_path="/")
        context = {
            "request": request,
            "user": request.user,
            "PEACHJAM_SETTINGS": SimpleNamespace(
                save_documents_enabled=False,
                save_searches_enabled=False,
                follows_enabled=False,
            ),
            "DISABLE_ACCOUNTS": True,
            "MY_LII": "My Peachjam",
            "sentry_enabled": False,
        }

        html = render_to_string("peachjam/user/_menu.html", context, request=request)

        self.assertNotIn(reverse("my_home"), html)
        self.assertNotIn(reverse("my_account"), html)
        self.assertNotIn(reverse("account_logout"), html)
        self.assertIn(reverse("admin:index"), html)

    def test_authenticated_header_hides_feature_links_without_permissions(self):
        request = RequestFactory().get("/")
        request.user = User.objects.first()
        request.htmx = SimpleNamespace(current_url_abs_path="/")
        context = {
            "request": request,
            "user": request.user,
            "PEACHJAM_SETTINGS": SimpleNamespace(
                save_documents_enabled=True,
                save_searches_enabled=True,
                follows_enabled=True,
            ),
            "DISABLE_ACCOUNTS": False,
            "MY_LII": "My Peachjam",
            "sentry_enabled": False,
        }

        html = render_to_string("peachjam/user/_menu.html", context, request=request)

        self.assertNotIn(reverse("folder_list"), html)
        self.assertNotIn(reverse("user_following_list"), html)
        self.assertNotIn(reverse("search:saved_search_list"), html)


class SignupViewTests(TestCase):
    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "AUTH_OTP": False, "DISABLE_ACCOUNTS": False}
    )
    def test_signup_view_login_link_includes_next_when_otp_disabled(self):
        response = self.client.get(reverse("account_signup"), {"next": "foo"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("account_login")}?next=foo"',
            html=False,
        )

    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "AUTH_OTP": False, "DISABLE_ACCOUNTS": False}
    )
    def test_login_view_signup_link_includes_next_when_otp_disabled(self):
        response = self.client.get(reverse("account_login"), {"next": "foo"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("account_signup")}?next=foo"',
            html=False,
        )

    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "AUTH_OTP": True, "DISABLE_ACCOUNTS": False}
    )
    def test_signup_view_redirects_to_login_when_otp_enabled(self):
        from peachjam.views.accounts import SignupView

        request = RequestFactory().get(reverse("account_signup"))
        response = SignupView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("account_login"))

    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "AUTH_OTP": True, "DISABLE_ACCOUNTS": False}
    )
    def test_signup_view_redirects_to_login_with_next_when_otp_enabled(self):
        response = self.client.get(reverse("account_signup"), {"next": "foo"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{reverse('account_login')}?next=foo")


class AccountPromptTemplateTests(TestCase):
    def render_template(self, template_name, context=None):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.htmx = SimpleNamespace(
            current_url_abs_path="/", current_url="http://testserver/"
        )
        base_context = {
            "request": request,
            "user": request.user,
            "DISABLE_ACCOUNTS": True,
            "next_url": "/",
            "SUPPORT_EMAIL": "support@example.com",
            "saved_search": SimpleNamespace(pk=False, is_subscription_locked=False),
            "taxonomy": SimpleNamespace(name="Restricted"),
            "lowest_product": None,
        }
        if context:
            base_context.update(context)
        return render_to_string(template_name, base_context, request=request)

    def test_download_403_hides_account_links_when_accounts_disabled(self):
        html = self.render_template("peachjam_search/_download_403.html")

        self.assertNotIn(reverse("account_login"), html)
        self.assertNotIn(reverse("account_signup"), html)

    def test_saved_document_modal_hides_login_button_when_accounts_disabled(self):
        html = self.render_template("peachjam/saved_document/_anon_modal.html")

        self.assertNotIn(reverse("account_login"), html)


@override_settings(
    PEACHJAM={**settings.PEACHJAM, "AUTH_OTP": True, "DISABLE_ACCOUNTS": True}
)
class DisabledAccountUrlsTests(TestCase):
    def setUp(self):
        super().setUp()
        from peachjam.urls import accounts

        self.accounts = reload(accounts)
        clear_url_caches()

    def test_disabled_patterns_are_prepended(self):
        disabled_patterns = self.accounts.urlpatterns[:2]

        self.assertEqual(disabled_patterns[0].pattern._route, "")
        self.assertEqual(disabled_patterns[1].pattern._route, "<path:path>")
        self.assertIs(
            disabled_patterns[0].callback.view_class,
            self.accounts.DisabledAccountUrlsView,
        )
        self.assertIs(
            disabled_patterns[1].callback.view_class,
            self.accounts.DisabledAccountUrlsView,
        )

    def test_otp_account_urls_are_still_registered_behind_disabled_catch_all(self):
        pattern_names = [
            pattern.name
            for pattern in self.accounts.urlpatterns
            if hasattr(pattern, "name") and pattern.name
        ]

        self.assertIn("account_signup", pattern_names)
        self.assertIn("account_request_login_code", pattern_names)
        self.assertIn("account_confirm_login_code", pattern_names)
