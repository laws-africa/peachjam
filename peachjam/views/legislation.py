from africanlii.registry import registry
from peachjam.models import Legislation
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class LegislationListView(FilteredDocumentListView):
    model = Legislation
    template_name = "africanlii/legislation_list.html"
    context_object_name = "documents"
    paginate_by = 20


@registry.register_doc_type("legislation")
class LegislationDetailView(BaseDocumentDetailView):
    model = Legislation
    template_name = "africanlii/legislation_detail.html"
