from django.apps import AppConfig
from django.conf import settings
from django.utils import timezone


class PeachJamConfig(AppConfig):
    name = "peachjam"

    def ready(self):
        import jazzmin.settings
        from countries_plus.models import Country
        from docpipe.matchers import CitationMatcher

        import peachjam.adapters  # noqa
        import peachjam.signals  # noqa
        from peachjam.helpers import get_country_absolute_url

        jazzmin.settings.THEMES["peachjam"] = "stylesheets/peachjam-jazzmin.css"

        Country.get_absolute_url = get_country_absolute_url
        # bump up the context for citation extraction
        CitationMatcher.text_prefix_length = CitationMatcher.text_suffix_length = 100

        # enforce timeouts and memory limits on soffice
        from docpipe import soffice

        soffice.TIMEOUT = 60 * 10  # 10 minutes
        soffice.SOFFICE_CMD = "timeout"
        soffice.SOFFICE_ARGS = [
            # send SIGKLL when the grace period is up
            "--signal=KILL",
            # send again 1s later
            "--kill-after=1s",
            # timeout in seconds, a bit longer than python's timeout
            f"{soffice.TIMEOUT + 30}s",
            # set resource limits
            "prlimit",
            # max memory (2 GB)
            f"--as={2 * 1024 * 1024 * 1024}",
            "--",
            # usual soffice command
            "soffice",
            "--headless",
        ]

        if not settings.DEBUG:
            from background_task.models import Task

            from peachjam.models import Ingestor
            from peachjam.tasks import (
                rank_works,
                send_timeline_email_alerts,
                update_user_timelines,
            )

            # always queue up ingestor tasks on application start
            for ingestor in Ingestor.objects.all():
                ingestor.queue_task()

            # run on sunday at 3am and then weekly after that
            run_at = timezone.now()
            run_at = (
                run_at + timezone.timedelta(days=(6 - run_at.weekday()) % 7)
            ).replace(hour=3, minute=0, second=0)
            rank_works(schedule=run_at, repeat=Task.WEEKLY)
            update_user_timelines(schedule=Task.HOURLY, repeat=Task.DAILY)
            send_timeline_email_alerts(schedule=Task.HOURLY, repeat=Task.DAILY)
