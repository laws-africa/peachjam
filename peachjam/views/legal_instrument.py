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
    queryset = LegalInstrument.objects.exclude(published=False).prefetch_related(
        "authors", "nature", "work"
    )

    def get_queryset(self):
        queryset = super(LegalInstrumentListView, self).get_queryset()
        return queryset.order_by("title")


@registry.register_doc_type("legal_instrument")
class LegalInstrumentDetailView(BaseDocumentDetailView):
    model = LegalInstrument
    template_name = "peachjam/legal_instrument_detail.html"
