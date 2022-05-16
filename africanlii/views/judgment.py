from django.views.generic import DetailView, ListView

from africanlii.models import Judgment
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class JudgmentListView(AuthedViewMixin, ListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        self.form = JudgmentFilterForm(self.request.GET)
        self.form.is_valid()
        queryset = Judgment.objects.all()
        return self.form.filter_queryset(queryset)

    def get_context_data(self, **kwargs):
        context = super(JudgmentListView, self).get_context_data(**kwargs)
        authors = list(set(Judgment.objects.values_list("court__name", flat=True)))
        context["authors"] = authors
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "document"
