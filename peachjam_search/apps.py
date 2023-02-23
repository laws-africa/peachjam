from django.apps import AppConfig


class PeachjamSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_search"

    def ready(self):
        import peachjam_search.signals  # noqa
        from peachjam_search.documents import setup_language_indexes

        setup_language_indexes()
