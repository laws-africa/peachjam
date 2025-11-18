from liiweb.views import HomePageView as BaseHomePageView
from peachjam.models import Article


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_articles"] = (
            Article.objects.prefetch_related("topics")
            .select_related("author")
            .order_by("-date")[:5]
        )

        return context
