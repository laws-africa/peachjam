from django.views.generic import TemplateView

from peachjam.models import Article, Judgment
from peachjam.models.generic_document import Legislation


class HomePageView(TemplateView):
    template_name = "lawlibrary/home.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context["recent_judgments"] = Judgment.objects.order_by("-date")[:5]
        context["recent_legislation"] = Legislation.objects.filter(
            metadata_json__stub=False
        ).order_by("-date")[:10]
        context["recent_articles"] = Article.objects.order_by("-date")[:5]

        return self.render_to_response(context)
