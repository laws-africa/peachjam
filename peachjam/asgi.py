"""
ASGI config for peachjam project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from uvicorn_worker import UvicornWorker


class DjangoUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "auto", "http": "auto", "lifespan": "off"}


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
