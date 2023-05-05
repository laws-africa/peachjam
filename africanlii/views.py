from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, TemplateView

from africanlii.forms import ESDocumentFilterForm
from peachjam.models import Article, CoreDocument, GenericDocument, Locality, Taxonomy
from peachjam.views import FilteredDocumentListView
from peachjam.views import HomePageView as BaseHomePageView
from peachjam.views import TaxonomyDetailView, TaxonomyFirstLevelView
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


def is_doc_index_topic(topic):
    """Return True if the topic is a doc index topic."""
    return topic.get_root().slug in settings.FEDERATED_DOC_INDEX_ROOTS


class DocIndexesListView(TemplateView):
    template_name = "africanlii/doc_indexes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["taxonomies"] = [get_object_or_404(Taxonomy, slug="case-index")]
        context["taxonomy_link_prefix"] = "indexes"
        return context


class DocIndexFirstLevelView(DetailView):
    template_name = "africanlii/doc_index_first_level.html"
    model = Taxonomy
    slug_url_kwarg = "topic"
    context_object_name = "taxonomy"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # send non-indexes topics back to the normal taxonomy view
        if not is_doc_index_topic(self.object):
            return redirect("first_level_taxonomy_list", topic=self.object.slug)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(taxonomy_link_prefix="indexes", **kwargs)


class DocIndexDetailView(TaxonomyDetailView):
    """Similar to the normal TaxonomyDetailView, except the document list is pulled from Elasticsearch."""

    template_name = "africanlii/doc_index_detail.html"
    form_class = ESDocumentFilterForm

    def get(self, request, *args, **kwargs):
        taxonomy = self.get_taxonomy()
        # send non-indexes topics back to the normal taxonomy view
        if not is_doc_index_topic(taxonomy):
            return redirect(
                "taxonomy_detail", topic=taxonomy.get_root().slug, child=taxonomy.slug
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["documents"] = self.decorate_documents(context["documents"])
        context["taxonomy_link_prefix"] = "indexes"
        context["doc_table_show_jurisdiction"] = True

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

    def add_facets(self, context):
        # prevent superclass from adding facets based on database queries
        pass


class CustomTaxonomyFirstLevelView(TaxonomyFirstLevelView):
    """Redirects index topics to the doc index view."""

    def get(self, request, *args, **kwargs):
        taxonomy = self.get_taxonomy()
        if is_doc_index_topic(taxonomy):
            return redirect("doc_index_first_level", topic=taxonomy.slug)
        return super().get(request, *args, **kwargs)


class CustomTaxonomyDetailView(TaxonomyDetailView):
    """Redirects index topics to the doc index view."""

    def get(self, request, *args, **kwargs):
        taxonomy = self.get_taxonomy()
        if is_doc_index_topic(taxonomy):
            return redirect(
                "doc_index_detail", topic=taxonomy.get_root().slug, child=taxonomy.slug
            )
        return super().get(request, *args, **kwargs)
