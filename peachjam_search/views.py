from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.filter_backends import (
    DefaultOrderingFilterBackend,
    FacetedFilterSearchFilterBackend,
    OrderingFilterBackend,
    SearchFilterBackend,
    SourceBackend,
)
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet

from peachjam.views import AuthedViewMixin
from peachjam_search.documents import SearchableDocument
from peachjam_search.serializers import SearchableDocumentSerializer


class SearchView(AuthedViewMixin, TemplateView):
    template_name = "peachjam_search/search.html"


class DocumentSearchViewSet(BaseDocumentViewSet):
    """API endpoint that allows document to be searched."""

    document = SearchableDocument
    serializer_class = SearchableDocumentSerializer
    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
        SearchFilterBackend,
        FacetedFilterSearchFilterBackend,
        SourceBackend,
    ]

    ordering_fields = {"date": "_date", "title": "title"}

    filter_fields = {
        "doc_type": "doc_type",
        "authoring_body": "authoring_body",
        "jurisdiction": "jurisdiction",
        "locality": "locality",
        "matter_type": "matter_type",
        "nature": "nature",
        "language": "language",
        "year": "year",
    }

    search_fields = (
        "title",
        "author",
        "jurisdiction",
        "locality",
        "citation",
        "matter_type",
        "content_html",
        "judges",
    )

    faceted_search_fields = {
        "doc_type": {
            "field": "doc_type",
        },
        "authoring_body": {
            "field": "authoring_body",
        },
        "jurisdiction": {
            "field": "jurisdiction",
        },
        "locality": {
            "field": "locality",
        },
        "matter_type": {
            "field": "matter_type",
        },
        "date": {
            "field": "date",
            "facet": DateHistogramFacet,
            "options": {"interval": "year"},
        },
        "year": {"field": "year"},
        "nature": {
            "field": "nature",
        },
        "language": {
            "field": "language",
        },
    }
