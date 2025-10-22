from django.conf import settings
from django.views.generic import TemplateView

from peachjam.models import CoreDocument, PeachJamSettings


class RobotsView(TemplateView):
    template_name = "peachjam/robots.txt"
    content_type = "text/plain"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        language_prefixes = [""]
        if len(settings.LANGUAGES) > 1:
            language_prefixes.extend(f"/{code}" for code, _ in settings.LANGUAGES)

        disallowed_content = []
        for frbr_uri in (
            CoreDocument.objects.filter(allow_robots=False)
            .values_list("work_frbr_uri", flat=True)
            .order_by()
            .distinct()
        ):
            normalized_uri = frbr_uri.rstrip("/")
            for prefix in language_prefixes:
                disallowed_content.append(f"Disallow: {prefix}{normalized_uri}/")
        context["disallowed_content"] = "\n".join(disallowed_content)
        context["extra_content"] = PeachJamSettings.load().robots_txt or ""

        return context
