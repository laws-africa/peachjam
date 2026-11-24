import os
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from peachjam.asgi import (
    get_uvicorn_worker_config,
    reject_unsupported_websocket_scope,
)


class UvicornWorkerConfigTests(SimpleTestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_ignores_concurrency_limit_when_environment_variable_is_unset(self):
        self.assertNotIn("limit_concurrency", get_uvicorn_worker_config())

    @patch.dict(os.environ, {"UVICORN_LIMIT_CONCURRENCY": "  "})
    def test_ignores_blank_concurrency_limit(self):
        self.assertNotIn("limit_concurrency", get_uvicorn_worker_config())

    @patch.dict(os.environ, {"UVICORN_LIMIT_CONCURRENCY": "10"})
    def test_adds_configured_concurrency_limit(self):
        self.assertEqual(10, get_uvicorn_worker_config()["limit_concurrency"])

    @patch.dict(os.environ, {"UVICORN_LIMIT_CONCURRENCY": "invalid"})
    def test_rejects_non_numeric_concurrency_limit(self):
        with self.assertRaisesRegex(
            ValueError, "UVICORN_LIMIT_CONCURRENCY must be a positive integer"
        ):
            get_uvicorn_worker_config()

    @patch.dict(os.environ, {"UVICORN_LIMIT_CONCURRENCY": "0"})
    def test_rejects_non_positive_concurrency_limit(self):
        with self.assertRaisesRegex(
            ValueError, "UVICORN_LIMIT_CONCURRENCY must be a positive integer"
        ):
            get_uvicorn_worker_config()


class RejectUnsupportedWebsocketScopeTests(SimpleTestCase):
    def test_closes_websocket_scope_without_calling_wrapped_app(self):
        called = False
        messages = []

        async def fake_app(scope, receive, send):
            nonlocal called
            called = True

        async def receive():
            return {"type": "websocket.connect"}

        async def send(message):
            messages.append(message)

        async_to_sync(reject_unsupported_websocket_scope)(
            fake_app,
            {"type": "websocket"},
            receive,
            send,
        )

        self.assertFalse(called)
        self.assertEqual([{"type": "websocket.close", "code": 1000}], messages)

    def test_passes_http_scope_through_to_wrapped_app(self):
        called = False

        async def fake_app(scope, receive, send):
            nonlocal called
            called = True

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            return None

        async_to_sync(reject_unsupported_websocket_scope)(
            fake_app,
            {"type": "http"},
            receive,
            send,
        )

        self.assertTrue(called)
