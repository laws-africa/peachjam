from django.apps import AppConfig


class AfricanliiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "africanlii"

    def ready(self):
        from docpipe.citations import AchprResolutionMatcher

        from peachjam.analysis.citations import citation_analyser

        # TODO: Act 5 of 2019 matcher, use whatever marker is appropriate
        # TODO: for plain text, we care about the regex and how to extract the right run and FRBR URI from it
        # TODO: for html, we care about the regex and how to markup the right run and FRBR URI from it
        citation_analyser.matchers.append(AchprResolutionMatcher)
