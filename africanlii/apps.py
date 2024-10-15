from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AfricanliiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "africanlii"

    def ready(self):
        from docpipe.citations import AchprResolutionMatcher, ActMatcher

        import africanlii.adapters  # noqa
        from liiweb.citations import MncMatcher
        from peachjam.analysis.citations import citation_analyser
        from peachjam.models import Author

        citation_analyser.matchers.append(AchprResolutionMatcher)
        citation_analyser.matchers.append(ActMatcher)
        citation_analyser.matchers.append(MncMatcher)

        Author.model_label = _("Regional Body / Author")
        Author.model_label_plural = _("Regional Bodies / Authors")
