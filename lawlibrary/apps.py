from django.apps import AppConfig


class LawlibraryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lawlibrary"

    def ready(self):
        from peachjam.models import Judgment, Legislation

        from .decorators import (
            LawLibraryLegislationDecorator,
            LawLibraryLJudgmentDecorator,
        )

        Judgment.decorator = LawLibraryLJudgmentDecorator()
        Legislation.decorator = LawLibraryLegislationDecorator()
