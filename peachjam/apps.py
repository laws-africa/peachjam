from django.apps import AppConfig
from django.conf import settings


class PeachJamConfig(AppConfig):
    name = "peachjam"

    def ready(self):
        if not settings.DEBUG:
            from peachjam.tasks import setup_ingestors

            setup_ingestors(repeat=60 * 60 * 24)
