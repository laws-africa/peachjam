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


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "africanlii.settings")

application = get_asgi_application()
