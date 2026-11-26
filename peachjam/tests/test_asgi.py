import asyncio
import os
from unittest.mock import Mock, patch

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from peachjam.asgi import (
    ASGIRequestDiagnostics,
    asgi_request_diagnostics_enabled,
    get_uvicorn_worker_config,
    reject_unsupported_websocket_scope,
    request_route_family,
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


class ASGIRequestDiagnosticsConfigTests(SimpleTestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_disabled_when_environment_variable_is_unset(self):
        self.assertFalse(asgi_request_diagnostics_enabled())

    @patch.dict(os.environ, {"ASGI_REQUEST_DIAGNOSTICS": " true "})
    def test_enabled_by_truthy_environment_variable(self):
        self.assertTrue(asgi_request_diagnostics_enabled())

    @patch.dict(os.environ, {"ASGI_REQUEST_DIAGNOSTICS": "false"})
    def test_disabled_by_non_truthy_environment_variable(self):
        self.assertFalse(asgi_request_diagnostics_enabled())


class RequestRouteFamilyTests(SimpleTestCase):
    def test_groups_public_document_routes_without_identifiers(self):
        self.assertEqual(
            "document-source",
            request_route_family(
                "/akn/ke/judgment/kehc/2024/1/eng@2024-01-01/source.pdf"
            ),
        )
        self.assertEqual(
            "document-social-image",
            request_route_family(
                "/akn/ke/judgment/kehc/2024/1/eng@2024-01-01/social-image.png"
            ),
        )
        self.assertEqual(
            "document",
            request_route_family("/akn/ke/judgment/kehc/2024/1/eng@2024-01-01"),
        )

    def test_groups_changed_provisions_and_top_level_routes(self):
        self.assertEqual(
            "changed-provisions",
            request_route_family(
                "/v1/p/kenyalaw.org/e/changed-provisions/akn/ke/act/2024/1"
            ),
        )
        self.assertEqual("search", request_route_family("/search"))
        self.assertEqual("home", request_route_family("/"))


class ASGIRequestDiagnosticsTests(SimpleTestCase):
    def run_diagnostics(self, diagnostics, scope=None):
        messages = []

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            messages.append(message)

        async_to_sync(diagnostics)(
            scope
            or {
                "type": "http",
                "method": "GET",
                "path": "/search",
            },
            receive,
            send,
        )
        return messages

    def test_logs_request_start_and_completion(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        logger = Mock()
        clock = Mock(side_effect=[10.0, 10.25])
        diagnostics = ASGIRequestDiagnostics(
            app, enabled=True, logger=logger, clock=clock
        )

        messages = self.run_diagnostics(diagnostics)

        self.assertEqual(200, messages[0]["status"])
        self.assertEqual(2, logger.info.call_count)
        start = logger.info.call_args_list[0].kwargs["extra"]
        complete = logger.info.call_args_list[1].kwargs["extra"]
        self.assertEqual("asgi_request_start", start["event"])
        self.assertEqual("search", start["route_family"])
        self.assertEqual(1, start["active_requests"])
        self.assertEqual("asgi_request_complete", complete["event"])
        self.assertEqual(200, complete["status_code"])
        self.assertEqual(250.0, complete["duration_ms"])
        self.assertEqual(1, complete["active_at_start"])
        self.assertEqual(0, complete["active_requests"])
        self.assertEqual(start["asgi_request_id"], complete["asgi_request_id"])

    def test_logs_exception_and_restores_active_request_count(self):
        class DiagnosticError(Exception):
            pass

        async def app(scope, receive, send):
            raise DiagnosticError

        logger = Mock()
        clock = Mock(side_effect=[5.0, 5.1])
        diagnostics = ASGIRequestDiagnostics(
            app, enabled=True, logger=logger, clock=clock
        )

        with self.assertRaises(DiagnosticError):
            self.run_diagnostics(diagnostics)

        complete = logger.info.call_args_list[1].kwargs["extra"]
        self.assertEqual("DiagnosticError", complete["exception_type"])
        self.assertIsNone(complete["status_code"])
        self.assertEqual(0, complete["active_requests"])
        self.assertEqual(0, diagnostics.active_requests)

    def test_disabled_diagnostics_pass_request_through_without_logging(self):
        called = False

        async def app(scope, receive, send):
            nonlocal called
            called = True

        logger = Mock()
        diagnostics = ASGIRequestDiagnostics(app, enabled=False, logger=logger)

        self.run_diagnostics(diagnostics)

        self.assertTrue(called)
        logger.info.assert_not_called()

    def test_tracks_overlapping_active_requests(self):
        logger = Mock()
        both_requests_started = asyncio.Event()
        release_requests = asyncio.Event()
        entered = 0

        async def app(scope, receive, send):
            nonlocal entered
            entered += 1
            if entered == 2:
                both_requests_started.set()
            await release_requests.wait()
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        diagnostics = ASGIRequestDiagnostics(app, enabled=True, logger=logger)

        async def call_app():
            async def receive():
                return {"type": "http.request"}

            async def send(message):
                return None

            await diagnostics(
                {"type": "http", "method": "GET", "path": "/search"},
                receive,
                send,
            )

        async def run_requests():
            requests = [asyncio.create_task(call_app()) for _ in range(2)]
            await both_requests_started.wait()
            self.assertEqual(2, diagnostics.active_requests)
            self.assertEqual(2, diagnostics.peak_active_requests)
            release_requests.set()
            await asyncio.gather(*requests)

        async_to_sync(run_requests)()
        self.assertEqual(0, diagnostics.active_requests)


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
