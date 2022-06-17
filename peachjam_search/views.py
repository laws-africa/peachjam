from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.filter_backends import (
    CompoundSearchFilterBackend,
    DefaultOrderingFilterBackend,
    FacetedFilterSearchFilterBackend,
    HighlightBackend,
    OrderingFilterBackend,
    SourceBackend,
)
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet

from peachjam_search.documents import SearchableDocument
from peachjam_search.serializers import SearchableDocumentSerializer

CACHE_SECS = 15 * 60


class SearchView(TemplateView):
    template_name = "peachjam_search/search.html"


class DocumentSearchViewSet(BaseDocumentViewSet):
    """API endpoint that allows document to be searched."""

    document = SearchableDocument
    serializer_class = SearchableDocumentSerializer
    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
        CompoundSearchFilterBackend,
        FacetedFilterSearchFilterBackend,
        SourceBackend,
        HighlightBackend,
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
        "content",
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

    highlight_fields = {
        "content": {
            "options": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fragment_size": 80,
                "number_of_fragments": 2,
            }
        },
    }

    @method_decorator(cache_page(CACHE_SECS))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
