from django.apps import AppConfig


class PeachjamSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_search"

    def ready(self):
        from background_task.models import Task

        import peachjam_search.signals  # noqa
        from peachjam_search.documents import setup_language_indexes
        from peachjam_search.tasks import prune_search_traces

        setup_language_indexes()

        # run in an hour and repeat daily
        prune_search_traces(schedule=Task.HOURLY, repeat=Task.DAILY)
