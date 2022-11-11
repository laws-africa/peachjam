from django.shortcuts import get_object_or_404

from peachjam.models import EntityProfile, Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class TaxonomyDetailView(FilteredDocumentListView):
    template_name = "peachjam/taxonomy_detail.html"

    def get(self, request, slug, *args, **kwargs):
        self.taxonomy = get_object_or_404(Taxonomy, slug=slug)
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(taxonomies__topic=self.taxonomy)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(taxonomy=self.taxonomy, **kwargs)
        context["entity_profile"] = EntityProfile.objects.filter(
            object_id=self.taxonomy.pk
        ).first()
        return context
