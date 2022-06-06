from django.views.generic import DetailView

from africanlii.models import GenericDocument
from africanlii.registry import registry
from africanlii.views.generic_views import FilteredDocumentListView


class GenericDocumentListView(FilteredDocumentListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument

    def get_queryset(self):
        queryset = super(GenericDocumentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(DetailView):
    model = GenericDocument
    slug_field = "expression_frbr_uri"
    slug_url_kwarg = "expression_frbr_uri"
    template_name = "africanlii/generic_document_detail.html"
    context_object_name = "document"
