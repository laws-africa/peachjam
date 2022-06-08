from django.views.generic import DetailView

from africanlii.models import LegalInstrument
from africanlii.registry import registry
from africanlii.views.generic_views import (
    DocumentVersionsMixin,
    FilteredDocumentListView,
)


class LegalInstrumentListView(FilteredDocumentListView):
    model = LegalInstrument
    template_name = "africanlii/legal_instrument_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super(LegalInstrumentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("legal_instrument")
class LegalInstrumentDetailView(DocumentVersionsMixin, DetailView):
    model = LegalInstrument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/legal_instrument_detail.html"
    context_object_name = "document"
