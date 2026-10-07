from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from peachjam.asgi import reject_unsupported_websocket_scope


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
