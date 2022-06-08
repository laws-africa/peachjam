from django.apps import AppConfig
from django.conf import settings


class PeachJamConfig(AppConfig):
    name = "peachjam"

    def ready(self):
        if settings.DEBUG:
            from peachjam.tasks import setup_ingestors

            setup_ingestors()
