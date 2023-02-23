from peachjam.models import Article, CoreDocument, Locality
from peachjam.views import DocumentListView, FilteredDocumentListView
from peachjam.views import HomePageView as BaseHomePageView
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


class AGPLegalInstrumentListView(FilteredDocumentListView):
    model = CoreDocument
    template_name = "peachjam/legal_instrument_list.html"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        return qs.filter(frbr_uri_doctype="act").prefetch_related("work", "nature")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["doc_table_show_doc_type"] = True
        return context


class AGPSoftLawListView(DocumentListView):
    template_name = "peachjam/soft_law_list.html"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.exclude(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs


class AGPReportsGuidesListView(DocumentListView):
    template_name = "peachjam/reports_guides_list.html"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.filter(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs


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
