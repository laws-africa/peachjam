from django.views.generic import DetailView

from africanlii.models import Judgment
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView
from peachjam.views import AuthedViewMixin


class JudgmentListView(AuthedViewMixin, FilteredDocumentListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super(FilteredDocumentListView, self).get_context_data(**kwargs)
        years = (
            Judgment.objects.values_list("date__year", flat=True).order_by().distinct()
        )
        context["years"] = years
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "document"
