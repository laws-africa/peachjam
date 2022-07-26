from django.views.generic import TemplateView

from peachjam.models import Judgment


class HomePageView(TemplateView):
    template_name = "lawlibrary/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        recent_judgments = Judgment.objects.order_by("-date")[:5]
        context["recent_judgments"] = recent_judgments

        return self.render_to_response(context)
