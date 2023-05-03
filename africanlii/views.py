from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from peachjam.models import (
    Article,
    CoreDocument,
    EntityProfile,
    GenericDocument,
    Locality,
    Taxonomy,
)
from peachjam.views import FilteredDocumentListView
from peachjam.views import HomePageView as BaseHomePageView
from peachjam.views.generic_views import DocumentListView
from peachjam_search.documents import SearchableDocument, get_search_indexes
from peachjam_search.views import DocumentSearchViewSet


class HomePageView(BaseHomePageView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        localities = Locality.objects.filter(jurisdiction__pk="AA").exclude(code="au")
        recent_articles = (
            Article.objects.prefetch_related("topics")
            .select_related("author")
            .order_by("-date")[:5]
        )

        context["localities"] = localities
        context["recent_articles"] = recent_articles
        context["recent_soft_law"] = GenericDocument.objects.exclude(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_reports_guides"] = GenericDocument.objects.filter(
            frbr_uri_doctype="doc"
        ).order_by("-date")[:5]
        context["recent_legal_instruments"] = CoreDocument.objects.filter(
            frbr_uri_doctype="act"
        ).order_by("-date")[:5]
        return context


class AGPLegalInstrumentListView(FilteredDocumentListView):
    model = CoreDocument
    template_name = "peachjam/legal_instrument_list.html"
    navbar_link = "legal_instruments"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        return qs.filter(frbr_uri_doctype="act").prefetch_related("work", "nature")

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["doc_table_show_doc_type"] = True
        return context


class AGPSoftLawListView(DocumentListView):
    template_name = "peachjam/soft_law_list.html"
    navbar_link = "soft_law"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.exclude(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs


class AGPReportsGuidesListView(DocumentListView):
    template_name = "peachjam/reports_guides_list.html"
    navbar_link = "reports_guides"

    def get_base_queryset(self):
        qs = super().get_base_queryset()
        qs = qs.filter(frbr_uri_doctype="doc").prefetch_related("work", "nature")
        return qs


class CaseIndexesListView(TemplateView):
    template_name = "africanlii/case_indexes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: how to lay this page out, correct links
        context["taxonomies"] = [get_object_or_404(Taxonomy, slug="case-index")]
        return context


class CaseIndexChildDetailView(DocumentListView):
    """Similar to the normal TaxonomyDetailView, except the document list is pulled from Elasticsearch."""

    # TODO: case-index-specific URLs in the taxonomy tree component

    template_name = "africanlii/case_index_detail.html"
    navbar_link = "taxonomy"
    context_object_name = "documents"

    def get(self, request, *args, **kwargs):
        if "/" in self.kwargs["topics"]:
            slug = self.kwargs["topics"].split("/")[-1]
            self.taxonomy = get_object_or_404(Taxonomy, slug=slug)
        else:
            self.taxonomy = get_object_or_404(Taxonomy, slug=self.kwargs["topics"])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["taxonomy"] = self.taxonomy
        context["entity_profile"] = EntityProfile.objects.filter(
            object_id=self.taxonomy.pk
        ).first()
        context["root"] = self.taxonomy
        ancestors = self.taxonomy.get_ancestors()
        if len(ancestors) > 1:
            context["root"] = ancestors[1]
        context["ancestors"] = ancestors
        context["root_taxonomy"] = context["root"].get_root().slug
        context["taxonomy_tree"] = list(context["root"].dump_bulk(context["root"]))
        context["first_level_taxonomy"] = context["taxonomy_tree"][0]["data"]["name"]
        context["is_leaf_node"] = not (context["taxonomy_tree"][0].get("children"))

        context["documents"] = self.decorate_documents(context["documents"])

        return context

    def decorate_documents(self, documents):
        """Ensure some extra fields that the view needs are on each result."""
        documents = list(documents)
        for r in documents:
            r["get_absolute_url"] = r["expression_frbr_uri"]
        return documents

    def get_base_queryset(self):
        index = get_search_indexes(SearchableDocument._index._name)
        search = (
            SearchableDocument.search(index=index)
            .source(exclude=DocumentSearchViewSet.source["excludes"])
            .filter("term", taxonomies=self.taxonomy.slug)
        )
        return search
