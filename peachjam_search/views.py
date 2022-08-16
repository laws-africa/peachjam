from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.filter_backends import (
    BaseSearchFilterBackend,
    CompoundSearchFilterBackend,
    DefaultOrderingFilterBackend,
    FacetedFilterSearchFilterBackend,
    HighlightBackend,
    OrderingFilterBackend,
    SourceBackend,
)
from django_elasticsearch_dsl_drf.filter_backends.search.query_backends import (
    BaseSearchQueryBackend,
)
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet
from elasticsearch_dsl.query import MatchPhrase, Q, SimpleQueryString
from rest_framework.permissions import AllowAny

from peachjam_search.documents import SearchableDocument
from peachjam_search.serializers import SearchableDocumentSerializer

CACHE_SECS = 15 * 60


class PageQueryBackend(BaseSearchQueryBackend):
    """Does a nested page search, and include highlights."""

    @classmethod
    def construct_search(cls, request, view, search_backend):
        queries = []
        for search_term in search_backend.get_search_query_params(request):
            print(search_term)
            queries.append(
                Q(
                    "nested",
                    path="pages",
                    query=Q(
                        "bool",
                        must=[
                            SimpleQueryString(
                                query=search_term,
                                default_operator="and",
                                quote_field_suffix=".exact",
                                fields=["pages.body"],
                            )
                        ],
                        should=[
                            MatchPhrase(pages__body={"query": search_term, "slop": 2}),
                        ],
                    ),
                    inner_hits={
                        "_source": ["pages.page_num"],
                        "highlight": {
                            "fields": {"pages.body": {}},
                            "pre_tags": ["<mark>"],
                            "post_tags": ["</mark>"],
                            "fragment_size": 80,
                            "number_of_fragments": 2,
                        },
                    },
                )
            )
        return queries


class CustomSearchBackend(BaseSearchFilterBackend):
    query_backends = [PageQueryBackend]

    def get_query_backends(self, request, view):
        return self.query_backends


class SearchView(TemplateView):
    template_name = "peachjam_search/search.html"


class DocumentSearchViewSet(BaseDocumentViewSet):
    """API endpoint that allows document to be searched."""

    document = SearchableDocument
    serializer_class = SearchableDocumentSerializer
    permission_classes = (AllowAny,)
    filter_backends = [
        OrderingFilterBackend,
        DefaultOrderingFilterBackend,
        CompoundSearchFilterBackend,
        FacetedFilterSearchFilterBackend,
        SourceBackend,
        HighlightBackend,
        CustomSearchBackend,
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
