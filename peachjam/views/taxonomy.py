from django.shortcuts import get_object_or_404

from peachjam.models import CoreDocument, Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class TaxonomyDetailView(FilteredDocumentListView):
    model = CoreDocument
    template_name = "peachjam/taxonomy_detail.html"
    context_object_name = "documents"
    paginate_by = 20

    def get(self, request, slug, *args, **kwargs):
        self.taxonomy = get_object_or_404(Taxonomy, slug=slug)
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(taxonomies__topic=self.taxonomy)

    def get_context_data(self, **kwargs):
        return super().get_context_data(taxonomy=self.taxonomy, **kwargs)
