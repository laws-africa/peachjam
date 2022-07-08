from django.apps import AppConfig


class AfricanliiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "africanlii"

    def ready(self):
        import africanlii.analysis  # noqa
