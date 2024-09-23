from django.apps import AppConfig
from django.conf import settings
from django.utils import timezone


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

            # run tomorrow at 2am and then daily after that
            run_at = (timezone.now() + timezone.timedelta(days=1)).replace(
                hour=2, minute=0, second=0
            )
            run_ingestors(schedule=run_at, repeat=Task.DAILY)

            # run on sunday at 3am and then weekly after that
            run_at = timezone.now()
            run_at = (
                run_at + timezone.timedelta(days=(6 - run_at.weekday()) % 7)
            ).replace(hour=3, minute=0, second=0)
            rank_works(schedule=run_at, repeat=Task.WEEKLY)
