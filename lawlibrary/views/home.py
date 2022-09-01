from django.views.generic import TemplateView

from peachjam.models import Judgment
from peachjam.models.generic_document import Legislation


class HomePageView(TemplateView):
    template_name = "lawlibrary/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        recent_judgments = Judgment.objects.order_by("-date")[:5]
        recent_legislation = Legislation.objects.filter(
            metadata_json__stub=False
        ).order_by("-date")[:10]
        context["recent_judgments"] = recent_judgments
        context["recent_legislation"] = recent_legislation

        return self.render_to_response(context)
