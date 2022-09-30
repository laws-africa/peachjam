from django.apps import AppConfig


class AfricanliiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "africanlii"

    def ready(self):
        from docpipe.citations import AchprResolutionMatcher, ActMatcher

        from liiweb.citations import MncMatcher
        from peachjam.analysis.citations import citation_analyser

        citation_analyser.matchers.append(AchprResolutionMatcher)
        citation_analyser.matchers.append(ActMatcher)
        citation_analyser.matchers.append(MncMatcher)
