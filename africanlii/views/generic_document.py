from django.views.generic import DetailView, ListView

from africanlii.models import GenericDocument
from africanlii.registry import registry
from peachjam.views import AuthedViewMixin


class GenericDocumentListView(AuthedViewMixin, ListView, FilteredDocumentListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument




@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(AuthedViewMixin, DetailView):
    model = GenericDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/generic_document_detail.html"
    context_object_name = "document"
