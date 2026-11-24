"""
ASGI config for peachjam project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from uvicorn_worker import UvicornWorker


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


async def reject_unsupported_websocket_scope(app, scope, receive, send):
    """Close unsolicited websocket upgrades before they reach Django's HTTP-only ASGI app."""
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1000})
        return

    await app(scope, receive, send)


async def application(scope, receive, send):
    await reject_unsupported_websocket_scope(django_application, scope, receive, send)
