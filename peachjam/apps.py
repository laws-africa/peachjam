from django.apps import AppConfig
from django.conf import settings


class PeachJamConfig(AppConfig):
    name = "peachjam"

    def ready(self):
        if not settings.DEBUG:
            import peachjam.adapters  # noqa
            from peachjam.tasks import run_ingestors

            run_ingestors(repeat=60 * 60 * 24)
