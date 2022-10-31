from django.conf import settings
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
from django_elasticsearch_dsl_drf.filter_backends.search.query_backends import (
    BaseSearchQueryBackend,
    SimpleQueryStringQueryBackend,
)
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet
from elasticsearch_dsl.query import MatchPhrase, Q, SimpleQueryString
from rest_framework.permissions import AllowAny

from peachjam_search.documents import SearchableDocument
from peachjam_search.serializers import SearchableDocumentSerializer

CACHE_SECS = 15 * 60


class NestedPageQueryBackend(BaseSearchQueryBackend):
    """Does a nested page search, and includes highlights."""

    @classmethod
    def construct_search(cls, request, view, search_backend):
        search_term = " ".join(search_backend.get_search_query_params(request))
        return [
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
        ]


class SearchFilterBackend(CompoundSearchFilterBackend):
    query_backends = [
        # Use ES's SimpleQueryString search support which allows quotes, +foo, -bar etc.
        SimpleQueryStringQueryBackend(),
        # Customised search on PDF page content
        NestedPageQueryBackend,
    ]


class SearchView(TemplateView):
    template_name = "peachjam_search/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["labels"] = {"author": "Regional body"}
        return context


class DocumentSearchViewSet(BaseDocumentViewSet):
    """API endpoint that allows document to be searched."""

    document = SearchableDocument
    serializer_class = SearchableDocumentSerializer
    permission_classes = (AllowAny,)
    filter_backends = [
        # lets the use specify order with ordering=field
        OrderingFilterBackend,
        # applies a default ordering
        DefaultOrderingFilterBackend,
        # supports filtering and facets by various fields
        FacetedFilterSearchFilterBackend,
        # do the actual search against the various fields
        SearchFilterBackend,
        # overrides the fields that are fetched from ES
        SourceBackend,
        HighlightBackend,
    ]

    # allowed and default ordering
    ordering_fields = {"date": "date", "title": "title"}
    ordering = ("_score", "date")

    filter_fields = {
        "doc_type": "doc_type",
        "court": "court",
        "author": "author",
        "jurisdiction": "jurisdiction",
        "locality": "locality",
        "matter_type": "matter_type",
        "nature": "nature",
        "language": "language",
        "year": "year",
        "is_most_recent": "is_most_recent",
    }

    search_fields = {
        "title": {"boost": 6},
        "author": None,
        "citation": {"boost": 4},
        "judges": None,
        "content": None,
        "court": None,
    }

    faceted_search_fields = {
        "doc_type": {
            "field": "doc_type",
            "options": {"size": 100},
        },
        "author": {
            "field": "author",
            "options": {"size": 100},
        },
        "jurisdiction": {
            "field": "jurisdiction",
            "options": {"size": 100},
        },
        "locality": {
            "field": "locality",
            "options": {"size": 100},
        },
        "matter_type": {
            "field": "matter_type",
            "options": {"size": 100},
        },
        "date": {
            "field": "date",
            "facet": DateHistogramFacet,
            "options": {"interval": "year", "size": 100},
        },
        "year": {"field": "year", "options": {"size": 100}},
        "nature": {
            "field": "nature",
            "options": {"size": 100},
        },
        "language": {
            "field": "language",
            "options": {"size": 100},
        },
        "court": {"field": "court", "options": {"size": 100}},
    }

    highlight_fields = {
        "content": {
            "options": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fragment_size": 80,
                "number_of_fragments": 2,
                "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
            }
        }
    }

    # TODO perhaps better to explicitly include specific fields
    source = {"excludes": ["pages", "content", "flynote", "headnote_holding"]}

    @method_decorator(cache_page(CACHE_SECS))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
