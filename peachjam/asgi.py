"""
ASGI config for peachjam project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import logging
import os
import time

from django.core.asgi import get_asgi_application
from uvicorn_worker import UvicornWorker

log = logging.getLogger(__name__)


def asgi_request_diagnostics_enabled():
    """Return whether detailed, per-request ASGI diagnostics are enabled."""
    return os.getenv("ASGI_REQUEST_DIAGNOSTICS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def request_route_family(path):
    """Group public request paths without logging identifiers or query strings."""
    path = path or "/"

    if path.startswith("/akn/"):
        if path.endswith(("/source", "/source.pdf")):
            return "document-source"
        if path.endswith("/social-image.png"):
            return "document-social-image"
        return "document"

    if path.startswith("/v1/p/") and "/changed-provisions/" in path:
        return "changed-provisions"

    first_segment = path.strip("/").partition("/")[0]
    return first_segment or "home"


class ASGIRequestDiagnostics:
    """Log request ownership and concurrency for a bounded ASGI diagnostic run.

    This is intentionally disabled unless ``ASGI_REQUEST_DIAGNOSTICS`` is set.
    Uvicorn rejects requests that exceed its concurrency limit before calling
    this application, so those rejections remain visible through Uvicorn's
    existing ``Exceeded concurrency limit.`` warning.
    """

    def __init__(self, app, enabled=None, logger=None, clock=None):
        self.app = app
        self.enabled = (
            asgi_request_diagnostics_enabled() if enabled is None else enabled
        )
        self.logger = logger or log
        self.clock = clock or time.monotonic
        self.active_requests = 0
        self.peak_active_requests = 0
        self.request_sequence = 0

    async def __call__(self, scope, receive, send):
        if not self.enabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        self.request_sequence += 1
        request_id = f"{os.getpid()}-{self.request_sequence}"
        self.active_requests += 1
        self.peak_active_requests = max(self.peak_active_requests, self.active_requests)
        active_at_start = self.active_requests
        started_at = self.clock()
        status_code = None
        exception_type = ""
        common = {
            "asgi_request_id": request_id,
            "method": scope.get("method", ""),
            "route_family": request_route_family(scope.get("path", "")),
        }

        self.logger.info(
            "ASGI request started",
            extra={
                **common,
                "event": "asgi_request_start",
                "active_requests": self.active_requests,
                "peak_active_requests": self.peak_active_requests,
            },
        )

        async def diagnostic_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, diagnostic_send)
        except BaseException as exception:
            exception_type = type(exception).__name__
            raise
        finally:
            duration_ms = round((self.clock() - started_at) * 1000, 3)
            self.active_requests -= 1
            self.logger.info(
                "ASGI request completed",
                extra={
                    **common,
                    "event": "asgi_request_complete",
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "active_at_start": active_at_start,
                    "active_requests": self.active_requests,
                    "peak_active_requests": self.peak_active_requests,
                    "exception_type": exception_type,
                },
            )


def get_uvicorn_worker_config():
    config = {"loop": "auto", "http": "auto", "lifespan": "off"}

    concurrency = os.getenv("UVICORN_LIMIT_CONCURRENCY", "").strip()
    if not concurrency:
        return config

    try:
        concurrency = int(concurrency)
    except ValueError as exception:
        raise ValueError(
            "UVICORN_LIMIT_CONCURRENCY must be a positive integer"
        ) from exception

    if concurrency < 1:
        raise ValueError("UVICORN_LIMIT_CONCURRENCY must be a positive integer")

    config["limit_concurrency"] = concurrency
    return config


class DjangoUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = get_uvicorn_worker_config()


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "liiweb.settings")

django_application = get_asgi_application()
diagnostic_application = ASGIRequestDiagnostics(django_application)


async def reject_unsupported_websocket_scope(app, scope, receive, send):
    """Close unsolicited websocket upgrades before they reach Django's HTTP-only ASGI app."""
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1000})
        return

    await app(scope, receive, send)


async def application(scope, receive, send):
    await reject_unsupported_websocket_scope(
        diagnostic_application, scope, receive, send
    )
