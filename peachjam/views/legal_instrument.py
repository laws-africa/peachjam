from peachjam.models import LegalInstrument
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegalInstrumentListView(FilteredDocumentListView):
    model = LegalInstrument
    template_name = "peachjam/legal_instrument_list.html"
    navbar_link = "legal_instruments"

    def get_queryset(self):
        queryset = LegalInstrument.objects.prefetch_related("author", "nature")
        return queryset.order_by("-date")


@registry.register_doc_type("legal_instrument")
class LegalInstrumentDetailView(BaseDocumentDetailView):
    model = LegalInstrument
    template_name = "peachjam/legal_instrument_detail.html"
