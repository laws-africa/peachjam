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

            from peachjam.models import Ingestor
            from peachjam.tasks import rank_works

            # always queue up ingestor tasks on application start
            for ingestor in Ingestor.objects.all():
                ingestor.queue_task()

            # run on sunday at 3am and then weekly after that
            run_at = timezone.now()
            run_at = (
                run_at + timezone.timedelta(days=(6 - run_at.weekday()) % 7)
            ).replace(hour=3, minute=0, second=0)
            rank_works(schedule=run_at, repeat=Task.WEEKLY)
