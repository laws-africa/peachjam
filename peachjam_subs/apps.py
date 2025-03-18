from django.apps import AppConfig


class PeachjamSubsConfig(AppConfig):
    name = "peachjam_subs"
    verbose_name = "Peachjam Subscriptions"

    def ready(self):
        import peachjam_subs.signals  # noqa
