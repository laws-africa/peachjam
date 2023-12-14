import copy

from django.conf import settings
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
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
from elasticsearch_dsl.connections import get_connection
from elasticsearch_dsl.query import MatchPhrase, Q, SimpleQueryString
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny

from peachjam.models import Author, Label, pj_settings
from peachjam_api.serializers import LabelSerializer
from peachjam_search.documents import SearchableDocument, get_search_indexes
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


class RankFeatureBackend(BaseSearchQueryBackend):
    @classmethod
    def construct_search(cls, request, view, search_backend):
        queries = []

        if pj_settings().pagerank_boost_value:
            # apply pagerank boost to the score using the saturation function
            kwargs = {"field": "ranking", "boost": pj_settings().pagerank_boost_value}
            if pj_settings().pagerank_pivot_value:
                kwargs["saturation"] = {"pivot": pj_settings().pagerank_pivot_value}

            queries.append(Q("rank_feature", **kwargs))

        return queries


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
                            default_operator="OR",
                            quote_field_suffix=".exact",
                            minimum_should_match="70%",
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

    must_backends = [MultiFieldSearchQueryBackend(), RankFeatureBackend()]

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
        search_placeholder_text = _("Search %(app_name)s") % {
            "app_name": settings.PEACHJAM["APP_NAME"]
        }
        context["labels"] = {
            "author": Author.model_label,
            "searchPlaceholder": search_placeholder_text,
            "documentLabels": LabelSerializer(Label.objects.all(), many=True).data,
        }
        context["show_jurisdiction"] = settings.PEACHJAM["SEARCH_JURISDICTION_FILTER"]
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
    # this means that at least 70% of terms must appear in ANY of the searched fields
    simple_query_string_options = {
        "default_operator": "OR",
        "minimum_should_match": "70%",
    }

    filter_fields = {
        "authors": "authors",
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
        "order_outcome": "order_outcome",
        "labels": "labels",
    }

    search_fields = {
        "title": {"boost": 8},
        "title_expanded": {"boost": 4},
        "authors": None,
        "citation": {"boost": 4},
        "judges": None,
        "content": None,
        "court": None,
        "alternative_names": {"boost": 4},
    }

    faceted_search_fields = {
        "doc_type": {
            "field": "doc_type",
            "options": {"size": 100},
        },
        "authors": {
            "field": "authors",
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
        "order_outcome": {"field": "order_outcome", "options": {"size": 100}},
        "labels": {"field": "labels", "options": {"size": 100}},
    }

    highlight_fields = {
        "title": {
            "options": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fragment_size": 0,
                "number_of_fragments": 0,
                "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
            }
        },
        "content": {
            "options": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fragment_size": 80,
                "number_of_fragments": 2,
                "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
            }
        },
    }

    # TODO perhaps better to explicitly include specific fields
    source = {"excludes": ["pages", "content", "flynote", "case_summary"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # search multiple language indexes
        self.index = get_search_indexes(self.document._index._name)
        self.search = self.search.index(self.index)

    def get_translatable_fields(self, request):
        # get language from request to use as suffix for translatable fields
        current_language_code = get_language_from_request(request)
        suffix = "_" + current_language_code

        self.filter_fields = copy.deepcopy(self.filter_fields)
        self.faceted_search_fields = copy.deepcopy(self.faceted_search_fields)

        translatable_fields = [
            "court",
            "nature",
            "registry",
            "order_outcome",
        ]

        for field in translatable_fields:
            self.filter_fields[field] = self.filter_fields[field] + suffix
            self.faceted_search_fields[field]["field"] = (
                self.faceted_search_fields[field]["field"] + suffix
            )

    def list(self, request, *args, **kwargs):
        # TODO: uncomment when we have reindexd the data
        # self.get_translatable_fields(request)
        resp = super().list(request, *args, **kwargs)

        # show debug information to this user?
        resp.data["can_debug"] = self.request.user.has_perm("peachjam.can_debug_search")

        return resp

    @action(detail=True)
    def explain(self, request, pk, *args, **kwargs):
        if not request.user.has_perm("peachjam.can_debug_search"):
            raise PermissionDenied()

        query = self.filter_queryset(self.get_queryset()).to_dict()["query"]
        # the index must be passed in as a query param otherwise we don't know which one to use
        index = request.GET.get("index") or self.index[0]

        es = get_connection(self.search._using)
        resp = es.explain(index, pk, {"query": query})
        return JsonResponse(resp)

    @vary_on_cookie
    @method_decorator(cache_page(CACHE_SECS))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
