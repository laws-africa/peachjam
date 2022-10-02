from peachjam.models import Article, Locality
from peachjam.views.home import HomePageView as BaseHomePageView


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        localities = Locality.objects.filter(jurisdiction__pk="AA").exclude(code="au")
        recent_articles = Article.objects.order_by("-date")[:5]
        return super().get_context_data(
            localities=localities, recent_articles=recent_articles
        )
