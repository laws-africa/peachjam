from django.views.generic import DetailView

from africanlii.models import Judgment
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class JudgmentListView(GenericListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super(JudgmentListView, self).get_context_data(**kwargs)
        courts = list(set(Judgment.objects.values_list("court__name", flat=True)))
        judges = list(set(Judgment.objects.values_list("judges", flat=True)))
        context["courts"] = courts
        context["judges"] = judges
        return context


@registry.register_doc_type("judgment")
class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "document"
