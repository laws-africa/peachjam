from peachjam.models import CoreDocument
from peachjam.views import DocumentListView, FilteredDocumentListView


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
