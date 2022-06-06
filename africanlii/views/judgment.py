from django.views.generic import DetailView

from africanlii.models import Judgment
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView


class JudgmentListView(FilteredDocumentListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        queryset = super(JudgmentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("judgment")
class JudgmentDetailView(DetailView):
    model = Judgment
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "document"
