from django.shortcuts import Http404, get_object_or_404
from django.views.generic import DetailView, TemplateView

from peachjam.models import Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class TaxonomyListView(TemplateView):
    template_name = "peachjam/taxonomy_list.html"
    navbar_link = "taxonomy"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["taxonomies"] = Taxonomy.dump_bulk()
        context["taxonomy_url"] = "taxonomy_detail"
        return self.render_to_response(context)


class TaxonomyFirstLevelView(DetailView):
    template_name = "peachjam/taxonomy_first_level_detail.html"
    model = Taxonomy
    slug_url_kwarg = "topic"
    context_object_name = "taxonomy"
    navbar_link = "taxonomy"

    def get_context_data(self, **kwargs):
        return super().get_context_data(taxonomy_link_prefix="taxonomy", **kwargs)


class TaxonomyDetailView(FilteredDocumentListView):
    template_name = "peachjam/taxonomy_detail.html"
    navbar_link = "taxonomy"

    def get(self, request, *args, **kwargs):
        self.taxonomy = self.get_taxonomy()
        return super().get(request, *args, **kwargs)

    def get_taxonomy(self):
        root = get_object_or_404(Taxonomy, slug=self.kwargs["topic"])
        taxonomy = get_object_or_404(Taxonomy, slug=self.kwargs["child"])
        # first check the root
        if taxonomy.get_root() != root:
            raise Http404()
        return taxonomy

    def get_base_queryset(self):
        # we want all documents that are in the current topic, and any of the topic's descendants
        topics = [self.taxonomy] + [t for t in self.taxonomy.get_descendants()]
        return (
            super().get_base_queryset().filter(taxonomies__topic__in=topics).distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = self.taxonomy
        context["entity_profile"] = self.taxonomy.get_entity_profile()
        context["root"] = self.taxonomy
        ancestors = self.taxonomy.get_ancestors()
        if len(ancestors) > 1:
            context["root"] = ancestors[1]
        context["ancestors"] = ancestors
        context["root_taxonomy"] = context["root"].get_root().slug
        context["taxonomy_tree"] = list(context["root"].dump_bulk(context["root"]))
        context["first_level_taxonomy"] = context["taxonomy_tree"][0]["data"]["name"]
        context["is_leaf_node"] = not (context["taxonomy_tree"][0].get("children"))
        context["taxonomy_link_prefix"] = "taxonomy"

        return context
