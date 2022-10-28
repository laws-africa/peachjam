from django.shortcuts import get_object_or_404
from django.views.generic import ListView, TemplateView

from peachjam.models import Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class PrimaryTaxonomyListView(TemplateView):
    template_name = "peachjam/primary_taxonomy_list.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["taxonomies"] = Taxonomy.get_tree()
        return self.render_to_response(context)


class SecondaryTaxonomyListView(ListView):
    template_name = "peachjam/secondary_taxonomy_list.html"
    model = Taxonomy

    def get(self, request, *args, **kwargs):
        self.taxonomy = get_object_or_404(
            Taxonomy, slug=self.kwargs["secondary_taxonomy_slug"]
        )
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(taxonomies__topic=self.taxonomy)

    def get_context_data(self, **kwargs):
        return super().get_context_data(taxonomy=self.taxonomy, **kwargs)


class TaxonomyDetailView(FilteredDocumentListView):
    template_name = "peachjam/taxonomy_detail.html"

    def get(self, request, *args, **kwargs):
        self.taxonomy = get_object_or_404(
            Taxonomy, slug=self.kwargs["secondary_taxonomy_slug"]
        )
        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(taxonomies__topic=self.taxonomy)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = self.taxonomy
        print(self.kwargs)
        context["current_child"] = get_object_or_404(
            Taxonomy, slug=self.kwargs["taxonomy_detail_slug"]
        )

        return context
