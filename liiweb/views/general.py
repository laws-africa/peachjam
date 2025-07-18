from django.views.generic import TemplateView

from peachjam.models import (
    Article,
    CourtClass,
    Gazette,
    Judgment,
    Legislation,
    Taxonomy,
)
from peachjam.views import HomePageView as PJHomePageView


class HomePageView(PJHomePageView):
    template_name = "liiweb/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["court_classes"] = CourtClass.objects.prefetch_related("courts")
        context["recent_judgments"] = (
            Judgment.objects.for_document_table()
            .exclude(published=False)
            .order_by("-date")[:10]
        )
        context["recent_legislation"] = (
            Legislation.objects.for_document_table()
            .exclude(published=False)
            .order_by("-date")[:10]
        )
        context["recent_gazettes"] = (
            Gazette.objects.for_document_table()
            .exclude(published=False)
            .order_by("-date")[:5]
        )
        context["taxonomies"] = Taxonomy.get_allowed_taxonomies(self.request.user)[
            "tree"
        ]
        context["taxonomy_url"] = "taxonomy_detail"
        context["recent_articles"] = (
            Article.objects.prefetch_related("topics", "author")
            .filter(published=True)
            .order_by("-date")[:5]
        )
        return context


class PocketlawView(TemplateView):
    template_name = "liiweb/pocketlaw.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(pocketlaw_version="1.0.7", **kwargs)
