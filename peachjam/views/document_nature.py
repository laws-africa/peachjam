from django.shortcuts import get_object_or_404

from peachjam.models import DocumentNature, GenericDocument
from peachjam.views.generic_views import FilteredDocumentListView


class DocumentNatureListView(FilteredDocumentListView):
    template_name = "peachjam/document_nature_list.html"
    model = GenericDocument
    queryset = GenericDocument.objects.prefetch_related("authors", "nature", "work")

    def get(self, *args, **kwargs):
        self.document_nature = get_object_or_404(
            DocumentNature, code=self.kwargs.get("nature")
        )
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nature"] = self.document_nature
        # disable nature facet
        context["facet_data"]["natures"] = []
        return context

    def get_base_queryset(self):
        return super().get_base_queryset().filter(nature=self.document_nature)
