from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase

from peachjam.account_signals import account_created
from peachjam.account_urls import account_url
from peachjam.customerio import track_account_created_signup_event


class AccountURLTests(SimpleTestCase):
    def test_default_adapter_keeps_urls_and_encodes_return_destination(self):
        request = RequestFactory().get("/")
        destination = "/documents/?q=one&tab=two"
        url = account_url(
            request,
            "/accounts/login/?mode=code",
            action="signup",
            permission="peachjam.add_saveddocument",
            next_url=destination,
        )
        self.assertEqual(
            parse_qs(urlsplit(url).query), {"mode": ["code"], "next": [destination]}
        )
        self.assertEqual(account_url(request, url, action="login"), url)

    def test_url_hook_receives_context_without_reading_session(self):
        class Request:
            @property
            def session(self):
                raise AssertionError("Public link accessed session")

        request = Request()
        with patch(
            "peachjam.auth.AccountAdapter.get_account_url", return_value="/custom/"
        ) as hook:
            result = Template(
                "{% load peachjam %}{% account_url target action='signup' permission='peachjam.add_saveddocument' %}"
            ).render(Context({"request": request, "target": "/accounts/signup/"}))
        self.assertEqual(result, "/custom/")
        hook.assert_called_once_with(
            request,
            "/accounts/signup/",
            action="signup",
            permission="peachjam.add_saveddocument",
        )

    def test_empty_form_extension_has_no_fields(self):
        rendered = Template('{% include "account/_extra_form_fields.html" %}').render(
            Context({})
        )
        self.assertEqual(rendered.strip(), "")


class AccountLifecycleTests(TestCase):
    fixtures = ["tests/languages"]

    def test_creation_signal_precedes_signup_event(self):
        user = User.objects.create_user("created@example.com")
        request = SimpleNamespace(session={})
        observed = []

        def receiver(sender, user, request, **kwargs):
            observed.append((user, request))

        account_created.connect(receiver, weak=False)
        try:
            with patch("peachjam.customerio.get_customerio") as cio:
                cio.return_value.track_user_signed_up.side_effect = lambda user: (
                    self.assertEqual(observed, [(user, request)])
                )
                track_account_created_signup_event(user, request=request)
        finally:
            account_created.disconnect(receiver)
