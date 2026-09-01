from datetime import timedelta
from importlib import reload
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from allauth.account.internal.flows.login_by_code import LoginCodeVerificationProcess
from allauth.account.models import Login
from allauth.account.stages import LoginByCodeStage
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import URLResolver, clear_url_caches, reverse
from django.urls.resolvers import RoutePattern
from django.utils import timezone
from languages_plus.models import Language

from peachjam.auth import (
    AccountAdapter,
    _patched_finish,
    _patched_send_by_email,
    create_all_users_permission_group_after_migrate,
    get_or_create_all_users_permission_group,
)
from peachjam.customerio import CustomerIO
from peachjam.models import OnboardingIntent, PracticeType


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

        with patch("peachjam.auth._original_finish") as mock_finish, patch(
            "peachjam.auth.track_account_created_signup_event"
        ) as mock_track_signup_event:
            mock_finish.return_value = "redirect"
            result = _patched_finish(proc, "/")

        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.username, "newuser@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(proc.state["user_id"], str(user.pk))
        self.assertEqual(proc._user, user)
        mock_finish.assert_called_once_with(proc, "/")
        mock_track_signup_event.assert_called_once_with(user)
        self.assertEqual(result, "redirect")

    def test_existing_user_not_duplicated(self):
        existing = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="somepass",
        )
        proc = self._make_process(state={"email": "existing@example.com"})
        proc.user = None

        with patch("peachjam.auth._original_finish") as mock_finish, patch(
            "peachjam.auth.track_account_created_signup_event"
        ) as mock_track_signup_event:
            mock_finish.return_value = "redirect"
            _patched_finish(proc, "/")

        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)
        self.assertEqual(proc._user, existing)
        existing.refresh_from_db()
        self.assertTrue(existing.has_usable_password())
        mock_track_signup_event.assert_not_called()

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


class AllUsersPermissionGroupMigrationTests(SimpleTestCase):
    @patch("peachjam.auth.get_or_create_all_users_permission_group")
    def test_group_is_created_after_migrations(self, create_group):
        create_all_users_permission_group_after_migrate()

        create_group.assert_called_once_with()


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


class LoginCodeCopyTests(SimpleTestCase):
    def test_login_code_email_uses_one_time_code_terminology(self):
        html = render_to_string(
            "peachjam/emails/account/email/login_code.email",
            {
                "APP_NAME": "Example LII",
                "PRIMARY_COLOUR": "#000000",
                "code": "123456",
                "site": "example.com",
            },
        )

        self.assertIn("Use this one-time code to log in to your account.", html)
        self.assertIn(
            "Enter the one-time code in your open browser window to continue.", html
        )
        self.assertIn("If you didn't request this one-time code", html)

    def test_login_code_success_message_uses_one_time_code_terminology(self):
        message = render_to_string(
            "account/messages/login_code_sent.txt", {"recipient": "test@example.com"}
        )

        self.assertEqual(
            message.strip(), "A one-time code has been sent to test@example.com."
        )


@override_settings(
    PEACHJAM={**settings.PEACHJAM, "DISABLE_ACCOUNTS": False},
)
class AccountAdapterOnboardingTests(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.profile = self.user.userprofile
        self.profile.onboarding_completed_at = None
        self.profile.onboarding_skipped_at = None
        self.profile.save()

    def post_login_destination(self, destination=None, signup=False):
        request = RequestFactory().get(reverse("account_login"))
        request.user = self.user

        with patch(
            "allauth.account.adapter.DefaultAccountAdapter.post_login",
            return_value=MagicMock(),
        ) as parent_post_login:
            AccountAdapter().post_login(
                request,
                self.user,
                email_verification="none",
                signal_kwargs={},
                email=None,
                signup=signup,
                redirect_url=destination,
            )

        return parent_post_login.call_args.kwargs["redirect_url"]

    def assert_onboarding_destination(self, destination, expected_next):
        parsed = urlparse(destination)
        self.assertEqual(parsed.path, reverse("account_onboard"))
        self.assertEqual(parse_qs(parsed.query)["next"], [expected_next])

    def test_user_without_names_is_sent_to_name_onboarding_after_login(self):
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save()

        destination = self.post_login_destination(reverse("about"))

        self.assert_onboarding_destination(destination, reverse("about"))

    def test_incomplete_user_is_sent_to_onboarding_after_login(self):
        destination = self.post_login_destination(reverse("about"))

        self.assert_onboarding_destination(destination, reverse("about"))

    def test_incomplete_user_is_sent_to_onboarding_after_signup(self):
        destination = self.post_login_destination(reverse("about"), signup=True)

        self.assert_onboarding_destination(destination, reverse("about"))

    def test_completed_user_continues_to_original_destination(self):
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.save()

        destination = self.post_login_destination(reverse("about"))

        self.assertEqual(destination, reverse("about"))

    def test_recently_skipped_user_continues_to_original_destination(self):
        self.profile.onboarding_skipped_at = timezone.now()
        self.profile.save()

        destination = self.post_login_destination(reverse("about"))

        self.assertEqual(destination, reverse("about"))

    def test_user_is_prompted_again_after_skip_cooldown(self):
        self.profile.onboarding_skipped_at = timezone.now() - timedelta(days=8)
        self.profile.save()

        destination = self.post_login_destination(reverse("about"))

        self.assert_onboarding_destination(destination, reverse("about"))

    def test_user_is_prompted_at_skip_cooldown_boundary(self):
        now = timezone.now()
        self.profile.onboarding_skipped_at = now - timedelta(days=7)
        self.profile.save()

        with patch("peachjam.models.user_profile.timezone.now", return_value=now):
            destination = self.post_login_destination(reverse("about"))

        self.assert_onboarding_destination(destination, reverse("about"))

    def test_onboarding_destination_is_not_nested(self):
        destination = self.post_login_destination(reverse("account_onboard"))

        self.assertEqual(destination, reverse("account_onboard"))


class OnboardingViewTests(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(pk=1)
        self.user.first_name = ""
        self.user.last_name = ""
        self.user.save()
        self.profile = self.user.userprofile
        self.profile.onboarding_completed_at = None
        self.profile.onboarding_skipped_at = None
        self.profile.save()
        self.intent = OnboardingIntent.objects.get(label="Research case law")
        self.second_intent = OnboardingIntent.objects.get(label="Research legislation")
        self.practice_type = PracticeType.objects.get(label="Sole practitioner")

    def login(self):
        self.client.force_login(self.user)

    def test_redirects_unauthenticated(self):
        response = self.client.get(reverse("account_onboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts", response["Location"])

    def test_shows_names_and_optional_questions_when_a_name_is_missing(self):
        self.login()

        response = self.client.get(reverse("account_onboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<label class="form-label" for="id_first_name">')
        self.assertContains(response, '<label class="form-label" for="id_last_name">')
        self.assertContains(response, "What are you hoping to do today?")
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'type="radio"')
        self.assertContains(response, 'class="form-check mb-2"')
        self.assertContains(response, 'class="form-check-label"')

    def test_shows_both_names_when_only_one_is_missing(self):
        self.user.first_name = "Jane"
        self.user.save()
        self.login()

        response = self.client.get(reverse("account_onboard"))

        self.assertContains(response, '<label class="form-label" for="id_first_name">')
        self.assertContains(response, '<label class="form-label" for="id_last_name">')
        self.assertContains(response, 'name="first_name" value="Jane"')

    def test_hides_both_names_when_both_are_already_set(self):
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.login()

        response = self.client.get(reverse("account_onboard"))

        self.assertNotContains(
            response, '<label class="form-label" for="id_first_name">'
        )
        self.assertNotContains(
            response, '<label class="form-label" for="id_last_name">'
        )
        self.assertContains(response, 'type="hidden" name="first_name" value="Jane"')
        self.assertContains(response, 'type="hidden" name="last_name" value="Doe"')
        self.assertContains(response, "What are you hoping to do today?")

    def test_completed_onboarding_redirects_when_names_are_set(self):
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.save()
        self.login()

        response = self.client.get(
            reverse("account_onboard"), data={"next": reverse("about")}
        )

        self.assertEqual(response["Location"], reverse("about"))

    def test_get_does_not_complete_or_skip_onboarding(self):
        self.login()

        self.client.get(reverse("account_onboard"))

        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.onboarding_completed_at)
        self.assertIsNone(self.profile.onboarding_skipped_at)

    def test_submit_saves_names_and_answers(self):
        self.login()

        with patch("peachjam.views.accounts.get_customerio") as get_customerio:
            response = self.client.post(
                reverse("account_onboard"),
                data={
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "onboarding_intents": [self.intent.pk, self.second_intent.pk],
                    "practice_type": self.practice_type.pk,
                    "action": "save",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertQuerySetEqual(
            self.profile.onboarding_intents.all(),
            [self.intent, self.second_intent],
            ordered=False,
        )
        self.assertEqual(self.profile.practice_type, self.practice_type)
        self.assertIsNotNone(self.profile.onboarding_completed_at)
        self.assertIsNone(self.profile.onboarding_skipped_at)
        get_customerio.return_value.track_onboarding_completed.assert_called_once_with(
            self.user
        )

    def test_customerio_user_details_include_onboarding_details(self):
        completed_at = timezone.now()
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.profile.onboarding_completed_at = completed_at
        self.profile.practice_type = self.practice_type
        self.profile.save()
        self.profile.onboarding_intents.set([self.intent, self.second_intent])

        details = CustomerIO().get_user_details(self.user)

        self.assertEqual(
            details["onboarding_intents"],
            [self.intent.label, self.second_intent.label],
        )
        self.assertEqual(details["onboarding_practice_type"], self.practice_type.label)
        self.assertEqual(
            details["onboarding_completed_at"], int(completed_at.timestamp())
        )
        self.assertIsNone(details["onboarding_skipped_at"])

    @patch("peachjam.customerio.CustomerIO.enabled", return_value=True)
    @patch("peachjam.customerio.analytics.identify")
    @patch("peachjam.customerio.analytics.track")
    def test_customerio_tracks_onboarding_completed_with_details(
        self, track, identify, enabled
    ):
        self.user.first_name = "Jane"
        self.user.last_name = "Doe"
        self.user.save()
        self.profile.onboarding_completed_at = timezone.now()
        self.profile.practice_type = self.practice_type
        self.profile.save()
        self.profile.onboarding_intents.set([self.intent])
        identify.reset_mock()
        track.reset_mock()

        CustomerIO().track_onboarding_completed(self.user)

        identify.assert_called_once()
        track.assert_called_once()
        self.assertEqual(track.call_args.args[1], "Onboarding completed")
        details = track.call_args.args[2]
        self.assertEqual(details["first_name"], "Jane")
        self.assertEqual(details["last_name"], "Doe")
        self.assertEqual(details["onboarding_intents"], [self.intent.label])
        self.assertEqual(details["onboarding_practice_type"], self.practice_type.label)

    def test_continue_requires_at_least_one_answer(self):
        self.login()

        response = self.client.post(
            reverse("account_onboard"),
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "onboarding_intents": [],
                "practice_type": "",
                "action": "save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose at least one option or select Not now.")
        self.assertNotContains(
            response, '<label class="form-label" for="id_first_name">'
        )
        self.assertNotContains(
            response, '<label class="form-label" for="id_last_name">'
        )
        self.assertContains(response, 'type="hidden" name="first_name" value="Jane"')
        self.assertContains(response, 'type="hidden" name="last_name" value="Doe"')
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertFalse(self.profile.onboarding_intents.exists())
        self.assertIsNone(self.profile.practice_type)
        self.assertIsNone(self.profile.onboarding_completed_at)

    def test_skip_saves_names_answers_and_sets_cooldown(self):
        self.login()

        with patch("peachjam.views.accounts.get_customerio") as get_customerio:
            response = self.client.post(
                reverse("account_onboard"),
                data={
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "onboarding_intents": [self.intent.pk],
                    "practice_type": self.practice_type.pk,
                    "action": "skip",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertEqual(self.user.last_name, "Doe")
        self.assertQuerySetEqual(
            self.profile.onboarding_intents.all(),
            [self.intent],
            ordered=False,
        )
        self.assertEqual(self.profile.practice_type, self.practice_type)
        self.assertIsNone(self.profile.onboarding_completed_at)
        self.assertIsNotNone(self.profile.onboarding_skipped_at)
        get_customerio.return_value.track_onboarding_completed.assert_not_called()

    def test_skip_requires_no_optional_answers(self):
        self.login()

        response = self.client.post(
            reverse("account_onboard"),
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "onboarding_intents": [],
                "practice_type": "",
                "action": "skip",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.onboarding_intents.exists())
        self.assertIsNone(self.profile.practice_type)
        self.assertIsNone(self.profile.onboarding_completed_at)
        self.assertIsNotNone(self.profile.onboarding_skipped_at)

    def test_skip_requires_both_names_when_either_is_missing(self):
        self.login()

        response = self.client.post(
            reverse("account_onboard"),
            data={
                "first_name": "Jane",
                "last_name": "",
                "onboarding_intents": [],
                "practice_type": "",
                "action": "skip",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("last_name", response.context["form"].errors)
        self.assertContains(response, '<label class="form-label" for="id_first_name">')
        self.assertContains(response, '<label class="form-label" for="id_last_name">')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Jane")
        self.assertEqual(self.user.last_name, "")

    def test_submit_preserves_next_url(self):
        self.login()
        next_url = reverse("about")

        response = self.client.post(
            reverse("account_onboard"),
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "onboarding_intents": [self.intent.pk],
                "practice_type": self.practice_type.pk,
                "next": next_url,
                "action": "save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    def test_account_profile_does_not_expose_onboarding_fields(self):
        self.profile.onboarding_intents.set([self.intent])
        self.profile.practice_type = self.practice_type
        self.profile.save()
        language = Language.objects.get(iso_639_1="en")
        self.login()

        response = self.client.get(reverse("edit_account"))

        self.assertNotContains(response, "What are you hoping to do today?")
        self.assertNotContains(
            response, "What best describes your role or organisation?"
        )
        self.assertNotContains(response, "Email alert frequency")

        response = self.client.get(reverse("my_account"))

        self.assertNotContains(response, self.intent.label)
        self.assertNotContains(response, self.practice_type.label)

        response = self.client.post(
            reverse("edit_account"),
            data={
                "first_name": "Janet",
                "last_name": "Doe",
                "preferred_language": language.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, "Janet")
        self.assertQuerySetEqual(
            self.profile.onboarding_intents.all(),
            [self.intent],
            ordered=False,
        )
        self.assertEqual(self.profile.practice_type, self.practice_type)


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

    def test_get_explains_where_to_find_the_login_code(self):
        request = self._make_request()
        view = self._setup_view(request, "test@example.com")
        response = view.get(request)

        self.assertContains(response, "Check your email for a one-time code")
        self.assertContains(response, "Please enter the one-time code we sent to")
        self.assertContains(response, "Request a new one-time code")
        self.assertContains(response, "Use a one-time code instead")

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

    def render_menu(self, accounts_enabled=True):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.htmx = SimpleNamespace(current_url_abs_path="/")
        context = {
            "request": request,
            "user": request.user,
            "PEACHJAM_SETTINGS": SimpleNamespace(accounts_enabled=accounts_enabled),
        }
        return render_to_string("peachjam/user/_menu.html", context, request=request)

    def test_header_shows_login_button_when_account_urls_enabled(self):
        html = self.render_menu(accounts_enabled=True)

        self.assertIn(f'href="{reverse("account_login")}?next=/"', html)

    def test_header_hides_login_button_when_account_urls_disabled(self):
        html = self.render_menu(accounts_enabled=False)

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
                accounts_enabled=False,
                save_documents_enabled=False,
                save_searches_enabled=False,
                follows_enabled=False,
            ),
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
                accounts_enabled=True,
                save_documents_enabled=True,
                save_searches_enabled=True,
                follows_enabled=True,
            ),
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
            "PEACHJAM_SETTINGS": SimpleNamespace(accounts_enabled=False),
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
        disabled_patterns = self.accounts.urlpatterns[5:7]

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

    def test_google_callback_remains_available(self):
        resolver = URLResolver(RoutePattern(""), self.accounts.urlpatterns)

        trailing_slash_match = resolver.resolve("google/login/callback/")
        no_trailing_slash_match = resolver.resolve("google/login/callback")

        self.assertIs(trailing_slash_match.func, self.accounts.oauth2_callback)
        self.assertIs(no_trailing_slash_match.func, self.accounts.oauth2_callback)

    def test_google_login_remains_available(self):
        resolver = URLResolver(RoutePattern(""), self.accounts.urlpatterns)

        match = resolver.resolve("google/login/")

        self.assertIs(match.func, self.accounts.oauth2_login)

    def test_logout_routes_remain_available(self):
        resolver = URLResolver(RoutePattern(""), self.accounts.urlpatterns)

        logout_match = resolver.resolve("logout/")
        logged_out_match = resolver.resolve("logged-out")

        self.assertIs(logout_match.func, self.accounts.account_logout)
        self.assertIs(logged_out_match.func.view_class, self.accounts.LoggedOutView)

    def test_other_account_urls_are_disabled(self):
        resolver = URLResolver(RoutePattern(""), self.accounts.urlpatterns)

        match = resolver.resolve("login/")

        self.assertIs(match.func.view_class, self.accounts.DisabledAccountUrlsView)

    def test_otp_account_urls_are_still_registered_behind_disabled_catch_all(self):
        pattern_names = [
            pattern.name
            for pattern in self.accounts.urlpatterns
            if hasattr(pattern, "name") and pattern.name
        ]

        self.assertIn("account_signup", pattern_names)
        self.assertIn("account_request_login_code", pattern_names)
        self.assertIn("account_confirm_login_code", pattern_names)
