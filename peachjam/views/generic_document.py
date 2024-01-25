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
    queryset = GenericDocument.objects.exclude(published=False).prefetch_related(
        "authors", "nature", "work"
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["doc_table_show_doc_type"] = True
        context["doc_count"] = self.get_queryset().count()
        return context

    def get_queryset(self):
        queryset = super(DocumentListView, self).get_queryset()
        return queryset.order_by("title")


@registry.register_doc_type("generic_document")
class DocumentDetailView(BaseDocumentDetailView):
    model = GenericDocument
    template_name = "peachjam/generic_document_detail.html"
