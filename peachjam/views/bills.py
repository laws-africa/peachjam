from peachjam.models import Bill
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class BillListView(FilteredDocumentListView):
    queryset = Bill.objects.all()
    model = Bill
    template_name = "peachjam/bill_list.html"
    navbar_link = "bills"


@registry.register_doc_type("bill")
class BillDetailView(BaseDocumentDetailView):
    model = Bill
    template_name = "peachjam/bill_detail.html"
