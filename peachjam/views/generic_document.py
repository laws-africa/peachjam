from peachjam.models import GenericDocument
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class GenericDocumentListView(FilteredDocumentListView):
    template_name = "peachjam/generic_document_list.html"
    model = GenericDocument
    navbar_link = "generic_documents"
    queryset = GenericDocument.objects.prefetch_related("author", "nature")

    def get_queryset(self):
        queryset = super(GenericDocumentListView, self).get_queryset()
        return queryset.order_by("-date")


@registry.register_doc_type("generic_document")
class GenericDocumentDetailView(BaseDocumentDetailView):
    model = GenericDocument
    template_name = "peachjam/generic_document_detail.html"
