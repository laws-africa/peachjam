from random import randint

from django.apps import AppConfig
from django.conf import settings
from django.utils import timezone


class PeachjamSubsConfig(AppConfig):
    name = "peachjam_subs"
    verbose_name = "Peachjam Subscriptions"

    def ready(self):
        from background_task.models import Task

        import peachjam_subs.metrics  # noqa
        import peachjam_subs.signals  # noqa
        from peachjam_subs.tasks import update_subscriptions

        if not settings.DEBUG:
            # schedule for 00:05 every day
            run_at = timezone.now()
            run_at = (run_at + timezone.timedelta(days=1)).replace(
                hour=0, minute=5 + randint(0, 10), second=0
            )
            update_subscriptions(schedule=run_at, repeat=Task.DAILY)
