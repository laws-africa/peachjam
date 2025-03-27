from django.http import HttpResponseForbidden
from django.shortcuts import Http404, get_object_or_404
from django.views.generic import DetailView, TemplateView
from guardian.shortcuts import get_objects_for_user

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
    # taxonomies may include legislation, so we want to show the latest expression only
    latest_expression_only = True

    def dispatch(self, request, *args, **kwargs):
        self.taxonomy = self.get_taxonomy()
        is_ancestor_restricted = self.taxonomy.get_ancestors().values_list(
            "restricted", flat=True
        )
        if self.taxonomy.restricted or any(is_ancestor_restricted):
            if not request.user.has_perm("peachjam.view_taxonomy", self.taxonomy):
                return HttpResponseForbidden()
        self.allowed_taxonomies = self.get_allowed_taxonomies(self.taxonomy)
        return super().dispatch(request, *args, **kwargs)

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

    def get_allowed_taxonomies(self, root, get_ids=False):
        if self.request.user.is_authenticated:
            allowed_taxonomies = set(
                get_objects_for_user(
                    self.request.user, "peachjam.view_taxonomy"
                ).values_list("id", flat=True)
            )
        else:
            allowed_taxonomies = []

        node_ids = []

        def filter_nodes(node):
            if not isinstance(node, dict):
                return node

            is_restricted = node.get("data", {}).get("restricted", False)
            is_allowed = node.get("id") in allowed_taxonomies

            if is_restricted and not is_allowed:
                return None

            node_ids.append(node["id"])
            if "children" in node:
                filtered_children = [
                    child
                    for child in (filter_nodes(child) for child in node["children"])
                    if child is not None
                ]

                if filtered_children:
                    node["children"] = filtered_children
                else:
                    node.pop("children", None)

            return node

        taxonomies = Taxonomy.dump_bulk(root)

        # Filter the entire tree
        filtered_taxonomies = [
            filtered_node
            for filtered_node in (filter_nodes(node) for node in taxonomies)
            if filtered_node is not None
        ]

        return {"tree": filtered_taxonomies, "pk_list": node_ids}

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
