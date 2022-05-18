from django.views.generic import DetailView, ListView

from africanlii.models import Legislation
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView
from peachjam.views import AuthedViewMixin


class LegislationListView(AuthedViewMixin, ListView, FilteredDocumentListView):
    model = Legislation
    template_name = "africanlii/legislation_list.html"
    context_object_name = "documents"
    paginate_by = 20


@registry.register_doc_type("legislation")
class LegislationDetailView(AuthedViewMixin, DetailView):
    model = Legislation
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/legislation_detail.html"
    context_object_name = "document"
