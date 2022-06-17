from africanlii.models import GenericDocument
from africanlii.registry import registry
from africanlii.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class GenericDocumentListView(FilteredDocumentListView):
    template_name = "africanlii/generic_document_list.html"
    context_object_name = "documents"
    paginate_by = 20
    model = GenericDocument

    def get_queryset(self):
        queryset = super(GenericDocumentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(BaseDocumentDetailView):
    model = GenericDocument
    template_name = "africanlii/generic_document_detail.html"
