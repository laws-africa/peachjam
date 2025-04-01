from django.apps import AppConfig


class PeachjamMLConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_ml"

    def ready(self):
        import peachjam_ml.signals  # noqa
