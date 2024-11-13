from peachjam.models import Bill
from peachjam.models.core_document import get_country_and_locality_or_404
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class BillListView(FilteredDocumentListView):
    model = Bill
    template_name = "peachjam/bill_list.html"
    navbar_link = "bills"


class PlaceBillListView(BillListView):
    template_name = "peachjam/place_bill_list.html"

    def get(self, *args, **kwargs):
        self.jurisdiction, self.locality = get_country_and_locality_or_404(
            kwargs["code"]
        )
        self.place = self.locality or self.jurisdiction
        return super().get(*args, **kwargs)

    def get_base_queryset(self):
        return (
            super()
            .get_base_queryset()
            .filter(jurisdiction=self.jurisdiction, locality=self.locality)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            place=self.place, jurisdiction=self.jurisdiction, locality=self.locality
        )
        return context


@registry.register_doc_type("bill")
class BillDetailView(BaseDocumentDetailView):
    model = Bill
    template_name = "peachjam/bill_detail.html"
