from django.apps import AppConfig
from django.conf import settings


class PeachJamConfig(AppConfig):
    name = "peachjam"

    def ready(self):
        import jazzmin.settings

        import peachjam.adapters  # noqa
        import peachjam.signals  # noqa

        jazzmin.settings.THEMES["peachjam"] = "stylesheets/peachjam-jazzmin.css"

        if not settings.DEBUG:
            from background_task.models import Task

            from peachjam.tasks import rank_works, run_ingestors

            run_ingestors(schedule=Task.DAILY, repeat=Task.DAILY)
            rank_works(schedule=Task.WEEKLY, repeat=Task.WEEKLY)
