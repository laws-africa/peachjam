from liiweb.views import HomePageView as BaseHomePageView
from peachjam.models import Judgment, Legislation


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["recent_judgments"] = Judgment.objects.order_by("-date")[:5]
        context["recent_legislation"] = Legislation.objects.filter(
            metadata_json__stub=False
        ).order_by("-date")[:10]
        return context
