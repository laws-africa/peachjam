from peachjam.models import Article, CoreDocument, GenericDocument, Locality
from peachjam.views import DocumentListView, FilteredDocumentListView
from peachjam.views import HomePageView as BaseHomePageView


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        localities = Locality.objects.filter(jurisdiction__pk="AA").exclude(code="au")
        recent_articles = (
            Article.objects.prefetch_related("topics")
            .select_related("author")
            .order_by("-date")[:5]
        )

        context["localities"] = localities
        context["recent_articles"] = recent_articles
        context["recent_soft_law"] = GenericDocument.objects.exclude(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_reports_guides"] = GenericDocument.objects.filter(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_legal_instruments"] = CoreDocument.objects.filter(
            frbr_uri_doctype="act"
        ).order_by("-date")[:5]
        return context


class AGPLegalInstrumentListView(FilteredDocumentListView):
    model = CoreDocument
    template_name = "peachjam/legal_instrument_list.html"
    navbar_link = "legal_instruments"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        return qs.filter(frbr_uri_doctype="act").prefetch_related("work", "nature")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["doc_table_show_doc_type"] = True
        return context


class AGPSoftLawListView(DocumentListView):
    template_name = "peachjam/soft_law_list.html"
    navbar_link = "soft_law"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.exclude(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs


class AGPReportsGuidesListView(DocumentListView):
    template_name = "peachjam/reports_guides_list.html"
    navbar_link = "reports_guides"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.filter(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs
