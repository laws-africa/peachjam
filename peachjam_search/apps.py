from django.apps import AppConfig
from django.conf import settings


class PeachjamSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_search"

    def ready(self):
        from background_task.models import Task

        import peachjam_search.signals  # noqa
        from peachjam_search.documents import setup_language_indexes

        setup_language_indexes()

        if not settings.DEBUG:
            from peachjam_search.tasks import prune_search_traces

            # run in an hour and repeat daily
            prune_search_traces(schedule=Task.HOURLY, repeat=Task.DAILY)
