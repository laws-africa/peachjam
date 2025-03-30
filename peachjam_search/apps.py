from django.apps import AppConfig, apps
from django.conf import settings


class PeachjamSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_search"

    def ready(self):
        from background_task.models import Task

        import peachjam_search.signals  # noqa
        from peachjam_search.documents import MultiLanguageIndexManager

        manager = MultiLanguageIndexManager.get_instance()
        manager.register_indexes()

        if settings.PEACHJAM["SEARCH_SEMANTIC"]:
            installed_apps = [a.label for a in apps.get_app_configs()]
            if "peachjam_ml" not in installed_apps:
                raise ImportError(
                    "peachjam_ml is required for semantic search. Please add it to settings.INSTALLED_APPS."
                )

        if not settings.DEBUG:
            from peachjam_search.tasks import prune_search_traces, update_saved_searches

            # run in an hour and repeat daily
            prune_search_traces(schedule=Task.HOURLY, repeat=Task.DAILY)
            update_saved_searches(schedule=Task.HOURLY, repeat=Task.DAILY)
