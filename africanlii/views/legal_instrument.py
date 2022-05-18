from django.views.generic import DetailView, ListView

from africanlii.models import LegalInstrument
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class LegalInstrumentListView(AuthedViewMixin, ListView):
    model = LegalInstrument
    template_name = "africanlii/legal_instrument_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        object_list = self.object_list
        context = self.get_context_data()

        authors = list(set(object_list.values_list("authoring_body__name", flat=True)))

        context["authors"] = authors
        return self.render_to_response(context)


@registry.register_doc_type("legal_instrument")
class LegalInstrumentDetailView(AuthedViewMixin, DetailView):
    model = LegalInstrument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/legal_instrument_detail.html"
    context_object_name = "document"
