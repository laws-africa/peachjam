from africanlii.models import Judgment
from africanlii.registry import registry
from africanlii.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class JudgmentListView(FilteredDocumentListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super(JudgmentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("judgment")
class JudgmentDetailView(BaseDocumentDetailView):
    model = Judgment
    template_name = "africanlii/judgment_detail.html"
