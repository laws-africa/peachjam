from africanlii.registry import registry
from peachjam.models import Legislation
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "peachjam/legislation_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super(LegislationListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "peachjam/legislation_detail.html"
