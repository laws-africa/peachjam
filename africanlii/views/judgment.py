from django.views.generic import DetailView, ListView

from africanlii.models import Judgment
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class JudgmentListView(AuthedViewMixin, ListView):
    model = Judgment
    template_name = "africanlii/judgment_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        object_list = self.object_list
        context = self.get_context_data()

        courts = list(set(object_list.values_list("court__name", flat=True)))

        judges = list(set(object_list.values_list("judge__name", flat=True)))

        context["courts"] = courts
        context["judges"] = judges
        return self.render_to_response(context)


@registry.register_doc_type("judgment")
class JudgmentDetailView(AuthedViewMixin, DetailView):
    model = Judgment
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/judgment_detail.html"
    context_object_name = "document"
