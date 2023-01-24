from django.shortcuts import get_object_or_404

from peachjam.models import DocumentNature, GenericDocument
from peachjam.views.generic_views import FilteredDocumentListView


class DocumentNatureListView(FilteredDocumentListView):
    template_name = "peachjam/document_nature_list.html"
    model = GenericDocument
    queryset = GenericDocument.objects.prefetch_related("author", "nature", "work")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["nature"] = get_object_or_404(
            DocumentNature, code=self.kwargs.get("nature")
        )

        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        nature = get_object_or_404(DocumentNature, code=self.kwargs.get("nature"))
        return queryset.filter(nature=nature)
