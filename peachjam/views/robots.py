from django.views.generic import TemplateView

from peachjam.models import CoreDocument


class RobotsView(TemplateView):
    template_name = "peachjam/robots.txt"
    content_type = "text/plain"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        disallowed_content = [
            f"Disallow: {frbr_uri}/"
            for frbr_uri in CoreDocument.objects.filter(allow_robots=False)
            .values_list("work_frbr_uri", flat=True)
            .order_by()
            .distinct()
        ]
        context["disallowed_content"] = "\n".join(disallowed_content)

        return context
