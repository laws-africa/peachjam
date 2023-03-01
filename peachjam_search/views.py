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

from peachjam_search.documents import ANALYZERS, SearchableDocument
from peachjam_search.serializers import SearchableDocumentSerializer

CACHE_SECS = 15 * 60


class MultiFieldSearchQueryBackend(SimpleQueryStringQueryBackend):
    """Supports searching across multiple fields.

    Specify zero or more query parameters such as search__title=foo
    """

    def construct_search(self, request, view, search_backend):
        view_search_fields = view.search_fields
        assert isinstance(view_search_fields, dict)

        # check for per-field search params
        query_params = {}
        for field in view_search_fields.keys():
            query = request.query_params.get(search_backend.search_param + "__" + field)
            if query:
                query_params[field] = query

        return [
            Q(
                self.query_type,
                query=search_term,
                fields=[self.get_field(field, view_search_fields[field])],
                **self.get_query_options(request, view, search_backend),
            )
            for field, search_term in query_params.items()
        ]


class NestedPageQueryBackend(BaseSearchQueryBackend):
    """Does a nested page search, and includes highlights."""

    @classmethod
    def construct_search(cls, request, view, search_backend):
        search_term = " ".join(search_backend.get_search_query_params(request))
        if not search_term:
            return []
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


class CrossFieldSimpleQueryStringBackend(SimpleQueryStringQueryBackend):
    """This implements a simple_query_string query across multiple fields, using AND logic for the terms
    in a field, but effectively OR (should) logic between the fields."""

    @classmethod
    def construct_search(cls, request, view, search_backend):
        query_fields = [
            cls.get_field(field, options)
            for field, options in view.search_fields.items()
        ]
        query_terms = search_backend.get_search_query_params(request)
        queries = []
        for search_term in query_terms[:1]:
            for field in query_fields:
                queries.append(
                    Q(
                        cls.query_type,
                        query=search_term,
                        fields=[field],
                        **cls.get_query_options(request, view, search_backend),
                    )
                )

        return queries


class SearchFilterBackend(CompoundSearchFilterBackend):
    """Custom search backend that builds our boolean query, based on two factors: an all-field search (simple),
    and a per-field (advanced) search. The two can also be combined.

    1. Simple: a SHOULD query (minimum_should_match=1), for:
       a. all the fields (individually)
       b. nested page content

    2. Advanced: a MUST query for the specified field(s).

    3. Combined simple and advanced, using both SHOULD and MUST from above.
    """

    must_backends = [MultiFieldSearchQueryBackend()]

    should_backends = [
        # Search each field individually using SimpleQueryString which allows quotes, +foo, -bar etc.
        CrossFieldSimpleQueryStringBackend,
        # Customised search on PDF page content
        NestedPageQueryBackend,
    ]

    def filter_queryset(self, request, queryset, view):
        # must queries
        must_queries = []
        for backend in self.must_backends:
            must_queries.extend(
                backend.construct_search(
                    request=request, view=view, search_backend=self
                )
            )

        # should queries
        should_queries = []
        for backend in self.should_backends:
            should_queries.extend(
                backend.construct_search(
                    request=request, view=view, search_backend=self
                )
            )

        return queryset.query(
            "bool",
            must=must_queries,
            should=should_queries,
            minimum_should_match=1 if should_queries else 0,
        )


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
    # this means that ALL terms must appear in ANY of the searched fields
    simple_query_string_options = {"default_operator": "AND"}

    filter_fields = {
        "author": "author",
        "court": "court",
        "date": "date",
        "doc_type": "doc_type",
        "is_most_recent": "is_most_recent",
        "jurisdiction": "jurisdiction",
        "language": "language",
        "locality": "locality",
        "matter_type": "matter_type",
        "nature": "nature",
        "year": "year",
        "judges": "judges",
        "registry": "registry",
        "attorneys": "attorneys",
    }

    search_fields = {
        "title": {"boost": 6},
        "author": None,
        "citation": {"boost": 4},
        "judges": None,
        "content": None,
        "court": None,
        "alternative_names": {"boost": 4},
        "registry": None,
        "attorneys": None,
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
        "judges": {"field": "judges", "options": {"size": 100}},
        "registry": {"field": "registry", "options": {"size": 100}},
        "attorneys": {"field": "attorneys", "options": {"size": 100}},
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # search multiple language indexes
        self.index = [self.document._index._name] + [
            f"{self.document._index._name}_{lang}" for lang in ANALYZERS.keys()
        ]
        self.search = self.search.index(self.index)

    @method_decorator(cache_page(CACHE_SECS))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
