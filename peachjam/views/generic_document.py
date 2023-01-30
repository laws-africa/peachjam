from peachjam.models import GenericDocument
from peachjam.registry import registry
from peachjam.views.generic_views import (
    BaseDocumentDetailView,
    FilteredDocumentListView,
)


class DocumentListView(FilteredDocumentListView):
    template_name = "peachjam/generic_document_list.html"
    model = GenericDocument
    navbar_link = "doc"
    queryset = GenericDocument.objects.prefetch_related("author", "nature", "work")

    def get_queryset(self):
        queryset = super(DocumentListView, self).get_queryset()
        return queryset.order_by("title")


@registry.register_doc_type("generic_document")
class DocumentDetailView(BaseDocumentDetailView):
    model = GenericDocument
    template_name = "peachjam/generic_document_detail.html"
