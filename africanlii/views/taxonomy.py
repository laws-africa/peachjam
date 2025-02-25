import datetime

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import gettext_lazy as _
from django.views.generic import DetailView, TemplateView
from elasticsearch_dsl.faceted_search import FacetedSearch, TermsFacet

from africanlii.forms import ESDocumentFilterForm
from peachjam.helpers import lowercase_alphabet
from peachjam.models import Taxonomy
from peachjam.views import TaxonomyDetailView, TaxonomyFirstLevelView
from peachjam_search.documents import MultiLanguageIndexManager, SearchableDocument
from peachjam_search.engine import SearchEngine


def is_doc_index_topic(topic):
    """Return True if the topic is a doc index topic."""
    return topic.get_root().slug in settings.FEDERATED_DOC_INDEX_ROOTS


class DocIndexesListView(TemplateView):
    template_name = "africanlii/doc_indexes.html"
    navbar_link = "doc_index"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        taxonomy = get_object_or_404(Taxonomy, slug="case-index")
        context["taxonomies"] = Taxonomy.dump_bulk(parent=taxonomy)
        context["taxonomy_url"] = "doc_index_detail"
        context["taxonomy_link_prefix"] = "indexes"
        return context


class DocIndexFirstLevelView(DetailView):
    template_name = "africanlii/doc_index_first_level.html"
    model = Taxonomy
    slug_url_kwarg = "topic"
    context_object_name = "taxonomy"
    navbar_link = "doc_index"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # send non-indexes topics back to the normal taxonomy view
        if not is_doc_index_topic(self.object):
            return redirect("first_level_taxonomy_list", topic=self.object.slug)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["taxonomy_link_prefix"] = "indexes"
        context["help_link"] = "federated-case-indexes-on-africanlii"
        return context


class DocIndexDetailView(TaxonomyDetailView):
    """Similar to the normal TaxonomyDetailView, except the document list is pulled from Elasticsearch."""

    template_name = "africanlii/doc_index_detail.html"
    form_class = ESDocumentFilterForm
    navbar_link = "doc_index"

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

        return context

    def decorate_documents(self, documents):
        """Ensure some extra fields that the view needs are on each result."""
        documents = list(documents)
        for r in documents:
            r["get_absolute_url"] = r["expression_frbr_uri"]
            if isinstance(r["date"], datetime.datetime):
                r["date"] = r["date"].date()
            else:
                r["date"] = datetime.datetime.strptime(r["date"], "%Y-%m-%d").date()
        return documents

    def get_base_queryset(self):
        indexes = MultiLanguageIndexManager.get_instance().get_all_search_index_names()
        search = SearchableDocument.search(index=indexes)
        engine = SearchEngine()
        engine.add_source(search)
        search = search.filter("term", taxonomies=self.taxonomy.slug)
        return search

    def get_queryset(self):
        search = self.filter_queryset(self.get_base_queryset(), filter_q=True)
        if self.latest_expression_only:
            search = search.filter("term", is_most_recent=True)
        return search

    def add_facets(self, context):
        """Add a limited set of facets pulled from ES."""
        faceted = FacetedSearch()
        faceted.index = (
            MultiLanguageIndexManager.get_instance().get_all_search_index_names()
        )
        faceted.facets = {
            "year": TermsFacet(field="year", size=100),
            "jurisdiction": TermsFacet(field="jurisdiction", size=100),
        }
        # add filters, but only on fields that we also facet on
        faceted = self.form.filter_faceted_search(faceted)
        # add non-facet filters
        search = self.form.filter_queryset(
            faceted.build_search(), exclude=["years", "jurisdictions"]
        )
        # add our primary taxonomy filter
        search = search.filter("term", taxonomies=self.taxonomy.slug)

        # don't actually get any documents, we just want the facets
        search = search[:0]

        res = search.execute()
        # this makes res.facets work
        res._faceted_search = faceted

        context["facet_data"] = {
            "jurisdictions": {
                "label": _("Judrisdictions"),
                "type": "checkbox",
                "options": [(j, j) for j, n, x in res.facets.jurisdiction],
                "values": self.request.GET.getlist("jurisdictions"),
            },
            "years": {
                "label": _("Years"),
                "type": "checkbox",
                "options": [
                    (str(y), y) for y, n, x in sorted(res.facets.year, reverse=True)
                ],
                "values": self.request.GET.getlist("years"),
            },
            "alphabet": {
                "label": _("Alphabet"),
                "type": "radio",
                "options": [(a, a) for a in lowercase_alphabet()],
                "values": self.request.GET.get("alphabet"),
            },
        }


class CustomTaxonomyFirstLevelView(TaxonomyFirstLevelView):
    """Redirects index topics to the doc index view."""

    def get(self, request, *args, **kwargs):
        taxonomy = self.get_object()
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
