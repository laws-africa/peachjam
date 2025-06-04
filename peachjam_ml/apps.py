from django.apps import AppConfig


class PeachjamMLConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "peachjam_ml"

    def ready(self):
        import peachjam_ml.signals  # noqa
        from peachjam.views import BaseDocumentDetailView

        from .handler import modify_document_detail_context

        BaseDocumentDetailView.modify_context.connect(modify_document_detail_context)
