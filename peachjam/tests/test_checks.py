import os
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from peachjam.checks import check_chat_configuration


@override_settings(
    PEACHJAM={
        "CHAT_ENABLED": True,
        "LAWSAFRICA_API_KEY": "laws-africa-key",
    }
)
class ChatConfigurationChecksTest(SimpleTestCase):
    def test_check_ignored_in_debug(self):
        with override_settings(DEBUG=True):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual([], check_chat_configuration(None))

    @override_settings(
        PEACHJAM={
            "CHAT_ENABLED": False,
            "LAWSAFRICA_API_KEY": "",
        }
    )
    def test_check_ignored_when_chat_disabled(self):
        with override_settings(DEBUG=False):
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual([], check_chat_configuration(None))

    def test_missing_chat_configuration_returns_errors(self):
        with override_settings(
            DEBUG=False,
            PEACHJAM={
                "CHAT_ENABLED": True,
                "LAWSAFRICA_API_KEY": "",
            },
        ):
            with patch.dict(os.environ, {}, clear=True):
                errors = check_chat_configuration(None)

        self.assertEqual(
            ["peachjam.E001", "peachjam.E002"], [error.id for error in errors]
        )
        self.assertEqual(
            'PEACHJAM["LAWSAFRICA_API_KEY"] must not be blank when CHAT_ENABLED is True.',
            errors[0].msg,
        )
        self.assertIn("LANGFUSE_PUBLIC_KEY", errors[1].msg)
        self.assertIn("LANGFUSE_SECRET_KEY", errors[1].msg)
        self.assertIn("LANGFUSE_TRACING_ENVIRONMENT", errors[1].msg)
        self.assertIn("OPENAI_API_KEY", errors[1].msg)

    def test_valid_chat_configuration_returns_no_errors(self):
        with override_settings(DEBUG=False):
            with patch.dict(
                os.environ,
                {
                    "LANGFUSE_PUBLIC_KEY": "public",
                    "LANGFUSE_SECRET_KEY": "secret",
                    "LANGFUSE_TRACING_ENVIRONMENT": "production",
                    "OPENAI_API_KEY": "openai-key",
                },
                clear=True,
            ):
                self.assertEqual([], check_chat_configuration(None))
