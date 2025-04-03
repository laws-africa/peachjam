from django.core.exceptions import PermissionDenied
from django.shortcuts import Http404, get_object_or_404
from django.views.generic import DetailView, TemplateView

from peachjam.models import Taxonomy
from peachjam.views.generic_views import FilteredDocumentListView


class TaxonomyListView(TemplateView):
    template_name = "peachjam/taxonomy_list.html"
    navbar_link = "taxonomy"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["taxonomies"] = Taxonomy.get_allowed_taxonomies(request.user)["tree"]
        context["taxonomy_url"] = "taxonomy_detail"
        return self.render_to_response(context)


class AllowedTaxonomyMixin:
    def dispatch(self, request, *args, **kwargs):
        self.taxonomy = self.get_taxonomy()
        is_ancestor_restricted = self.taxonomy.get_ancestors().values_list(
            "restricted", flat=True
        )
        if self.taxonomy.restricted or any(is_ancestor_restricted):
            if not request.user.has_perm("peachjam.view_taxonomy", self.taxonomy):
                raise PermissionDenied
        self.allowed_taxonomies = Taxonomy.get_allowed_taxonomies(
            request.user, root=self.taxonomy
        )
        return super().dispatch(request, *args, **kwargs)


class TaxonomyFirstLevelView(AllowedTaxonomyMixin, DetailView):
    template_name = "peachjam/taxonomy_first_level_detail.html"
    model = Taxonomy
    slug_url_kwarg = "topic"
    context_object_name = "taxonomy"
    navbar_link = "taxonomy"

    def get_taxonomy(self):
        return self.get_object()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["children"] = self.object.get_allowed_children(self.request.user)
        context["taxonomy_link_prefix"] = "taxonomy"
        return context


class TaxonomyDetailView(AllowedTaxonomyMixin, FilteredDocumentListView):
    template_name = "peachjam/taxonomy_detail.html"
    navbar_link = "taxonomy"
    # taxonomies may include legislation, so we want to show the latest expression only
    latest_expression_only = True

    def get_taxonomy(self):
        root = get_object_or_404(Taxonomy, slug=self.kwargs["topic"])
        taxonomy = get_object_or_404(Taxonomy, slug=self.kwargs["child"])
        # first check the root
        if taxonomy.get_root() != root:
            raise Http404()
        return taxonomy

    def get_base_queryset(self):
        # we want all documents that are in the current topic, and any of the topic's descendants
        topics = self.allowed_taxonomies["pk_list"]
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
        context["taxonomy_tree"] = self.allowed_taxonomies["tree"]
        context["first_level_taxonomy"] = context["taxonomy_tree"][0]["data"]["name"]
        context["is_leaf_node"] = not (context["taxonomy_tree"][0].get("children"))
        context["taxonomy_link_prefix"] = "taxonomy"

        return context
