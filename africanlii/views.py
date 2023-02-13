from peachjam.models import Article, Locality
from peachjam.views.home import HomePageView as BaseHomePageView
from peachjam.views.legislation import LegislationListView


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        localities = Locality.objects.filter(jurisdiction__pk="AA").exclude(code="au")
        recent_articles = (
            Article.objects.prefetch_related("topics")
            .select_related("author")
            .order_by("-date")[:5]
        )
        return super().get_context_data(
            localities=localities, recent_articles=recent_articles
        )


class AGPLegislationListView(LegislationListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        localities = list(
            {
                doc_n
                for doc_n in self.form.filter_queryset(
                    self.get_base_queryset(), exclude="localities"
                ).values_list("locality__name", flat=True)
                if doc_n
            }
        )

        context["facet_data"]["localities"] = localities

        return context
