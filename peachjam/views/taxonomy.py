from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, TemplateView

from peachjam.models import Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class TopLevelTaxonomyListView(TemplateView):
    template_name = "peachjam/top_level_taxonomy_list.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["taxonomies"] = Taxonomy.get_tree()
        return self.render_to_response(context)


class FirstLevelTaxonomyDetailView(DetailView):
    template_name = "peachjam/first_level_taxonomy_detail.html"
    model = Taxonomy
    slug_url_kwarg = "topic"
    context_object_name = "taxonomy"


class TaxonomyDetailView(FilteredDocumentListView):
    template_name = "peachjam/taxonomy_detail.html"

    def get(self, request, *args, **kwargs):

        if "/" in self.kwargs["topics"]:
            slug = self.kwargs["topics"].split("/")[-1]
            self.taxonomy = get_object_or_404(Taxonomy, slug=slug)
        else:
            self.taxonomy = get_object_or_404(Taxonomy, slug=self.kwargs["topics"])

        return super().get(request, *args, **kwargs)

    def get_base_queryset(self):
        return super().get_base_queryset().filter(taxonomies__topic=self.taxonomy)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = self.taxonomy
        context["root"] = self.taxonomy
        ancestors = self.taxonomy.get_ancestors()
        if len(ancestors) > 1:
            context["root"] = ancestors[1]
        context["ancestors"] = ancestors
        context["root_taxonomy"] = context["root"].get_root().slug
        context["taxonomy_tree"] = list(context["root"].dump_bulk(context["root"]))
        return context
