import copy

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.views.generic import TemplateView
from django_elasticsearch_dsl_drf.filter_backends import (
    DefaultOrderingFilterBackend,
    FacetedFilterSearchFilterBackend,
    HighlightBackend,
    OrderingFilterBackend,
    SourceBackend,
)
from django_elasticsearch_dsl_drf.filter_backends.search.base import (
    BaseSearchFilterBackend,
)
from django_elasticsearch_dsl_drf.pagination import PageNumberPagination, Paginator
from django_elasticsearch_dsl_drf.viewsets import BaseDocumentViewSet
from elasticsearch_dsl import DateHistogramFacet
from elasticsearch_dsl.connections import get_connection
from elasticsearch_dsl.query import MatchPhrase, Q, SimpleQueryString
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import GenericViewSet

from peachjam.models import Author, CourtRegistry, Judge, Label, pj_settings
from peachjam_api.serializers import LabelSerializer
from peachjam_search.documents import SearchableDocument, get_search_indexes
from peachjam_search.models import SearchTrace
from peachjam_search.serializers import (
    SearchableDocumentSerializer,
    SearchClickSerializer,
)

CACHE_SECS = 15 * 60


class RobustPaginator(Paginator):
    max_results = 10_000

    @cached_property
    def num_pages(self):
        # clamp the page number to prevent exceeding max_results
        return min(super().num_pages, (self.max_results - 1) // self.per_page)


class CustomPageNumberPagination(PageNumberPagination):
    # NB: if this changes, update pageSize in peachjam/js/components/FindDocuments/index.vue
    page_size = 10
    django_paginator_class = RobustPaginator


class MainSearchBackend(BaseSearchFilterBackend):
    """A search backend that builds the core query.

    It is a combination of MUST (AND) queries and SHOULD (OR) queries.
    """

    pages_inner_hits = {
        "_source": ["pages.page_num"],
        "highlight": {
            "fields": {"pages.body": {}, "pages.body.exact": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 80,
            "number_of_fragments": 2,
        },
    }

    provisions_inner_hits = {
        "_source": [
            "provisions.title",
            "provisions.id",
            "provisions.parent_titles",
            "provisions.parent_ids",
        ],
        "highlight": {
            "fields": {"provisions.body": {}, "provisions.body.exact": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 80,
            "number_of_fragments": 2,
        },
    }

    query = None

    def get_field(self, view, field):
        options = view.search_fields.get(field, {}) or {}
        if "boost" in options:
            return f'{field}^{options["boost"]}'
        return field

    def filter_queryset(self, request, queryset, view):
        """Build the actual search queries."""
        # the basic query for a simple search
        self.query = " ".join(self.get_search_query_params(request))

        must_queries = []
        must_queries.extend(self.build_rank_feature_queries(request, view))
        must_queries.extend(self.build_per_field_queries(request, view))

        should_queries = []
        if self.is_advanced_search(request, view):
            # these handle advanced search, and can't be combined with advanced search because they both
            # build queries to return nested content, and ES complains if multiple queries try to return the
            # same nested content fields
            must_queries.extend(self.build_advanced_all_queries(request, view))
            must_queries.extend(self.build_advanced_content_queries(request, view))
        else:
            # these handle basic search
            should_queries.extend(self.build_basic_queries(request, view))
            should_queries.extend(self.build_content_phrase_queries(request, view))
            should_queries.extend(self.build_nested_page_queries(request, view))
            should_queries.extend(self.build_nested_provision_queries(request, view))

        return queryset.query(
            "bool",
            must=must_queries,
            should=should_queries,
            minimum_should_match=1 if should_queries else 0,
        )

    def is_advanced_search(self, request, view):
        # it's an advanced search if any of the search__* query parameters are present
        return any(
            request.query_params.get(self.search_param + "__" + field)
            for field in list(view.search_fields.keys()) + ["all"]
        )

    def build_rank_feature_queries(self, request, view):
        """Apply a rank_feature query to boost the score based on the ranking field."""
        if pj_settings().pagerank_boost_value:
            # apply pagerank boost to the score using the saturation function
            kwargs = {"field": "ranking", "boost": pj_settings().pagerank_boost_value}
            if pj_settings().pagerank_pivot_value:
                kwargs["saturation"] = {"pivot": pj_settings().pagerank_pivot_value}
            return [Q("rank_feature", **kwargs)]
        return []

    def build_per_field_queries(self, request, view):
        """Supports searching across multiple fields. Specify zero or more query parameters such as search__title=foo"""
        queries = []

        for field in view.search_fields.keys():
            if field == "content":
                # advanced search on the "content" field (which must include pages and provisions too), is handled
                # by build_advanced_content_queries
                continue
            query = request.query_params.get(self.search_param + "__" + field)
            if query:
                queries.append(
                    SimpleQueryString(
                        query=query,
                        fields=[self.get_field(view, field)],
                        **view.advanced_simple_query_string_options,
                    )
                )

        return queries

    def build_basic_queries(self, request, view):
        """This implements a simple_query_string query across multiple fields, using AND logic for the terms
        in a field, but effectively OR (should) logic between the fields."""
        if not self.query:
            return []

        query_fields = [
            self.get_field(view, field) for field, options in view.search_fields.items()
        ]
        queries = [
            SimpleQueryString(
                query=self.query,
                fields=[field],
                **view.simple_query_string_options,
            )
            for field in query_fields
        ]

        return queries

    def build_content_phrase_queries(self, request, view):
        """Adds a best-effort phrase match query on the content field."""
        if not self.query:
            return []
        return [MatchPhrase(content={"query": self.query, "slop": 2})]

    def build_advanced_all_queries(self, request, view):
        """Build queries for search__all (advanced search across all fields). Similar logic to build_basic_queries,
        but all terms are required by default."""
        query = request.query_params.get(self.search_param + "__all")
        if not query:
            return []

        query_fields = [
            self.get_field(view, field) for field, options in view.search_fields.items()
        ]
        return [
            Q(
                "bool",
                minimum_should_match=1,
                should=[
                    SimpleQueryString(
                        query=query,
                        fields=[field],
                        **view.advanced_simple_query_string_options,
                    )
                    for field in query_fields
                ]
                + self.build_advanced_content_query(view, query),
            )
        ]

    def build_advanced_content_queries(self, request, view):
        """Adds advanced search queries for search__content, which searches across content, pages.body and
        provisions.body."""
        query = request.query_params.get(self.search_param + "__content")

        # don't allow search__content and search__all to clash, only one is needed to search content fields
        if query and request.query_params.get(self.search_param + "__all"):
            return []

        if query:
            return [
                Q(
                    "bool",
                    minimum_should_match=1,
                    should=self.build_advanced_content_query(view, query),
                )
            ]
        return []

    def build_advanced_content_query(self, view, query):
        # TODO: negative queries don't work, because they must be applied to the whole content, not just a
        # particular page or provision
        return [
            # content
            SimpleQueryString(
                query=query,
                fields=["content"],
                **view.advanced_simple_query_string_options,
            ),
            # pages.body
            Q(
                "nested",
                path="pages",
                inner_hits=self.pages_inner_hits,
                query=SimpleQueryString(
                    query=query,
                    fields=["pages.body"],
                    quote_field_suffix=".exact",
                    **view.advanced_simple_query_string_options,
                ),
            ),
            # provisions.body
            Q(
                "nested",
                path="provisions",
                inner_hits=self.provisions_inner_hits,
                query=Q(
                    "bool",
                    should=[
                        SimpleQueryString(
                            query=query,
                            fields=["provisions.body"],
                            quote_field_suffix=".exact",
                            **view.advanced_simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.title^4", "provisions.parent_titles^2"],
                            **view.advanced_simple_query_string_options,
                        ),
                    ],
                ),
            ),
        ]

    def build_nested_page_queries(self, request, view):
        """Does a nested page search, and includes highlights."""
        if not self.query:
            return []

        return [
            Q(
                "nested",
                path="pages",
                inner_hits=self.pages_inner_hits,
                query=Q(
                    "bool",
                    must=[
                        SimpleQueryString(
                            query=self.query,
                            fields=["pages.body"],
                            quote_field_suffix=".exact",
                            **view.simple_query_string_options,
                        )
                    ],
                    should=[
                        MatchPhrase(pages__body={"query": self.query, "slop": 2}),
                    ],
                ),
            )
        ]

    def build_nested_provision_queries(self, request, view):
        """Does a nested provision search, and includes highlights."""
        if not self.query:
            return []

        return [
            Q(
                "nested",
                path="provisions",
                inner_hits=self.provisions_inner_hits,
                query=Q(
                    "bool",
                    should=[
                        MatchPhrase(provisions__body={"query": self.query, "slop": 2}),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.body"],
                            quote_field_suffix=".exact",
                            **view.simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.title^4", "provisions.parent_titles^2"],
                            **view.simple_query_string_options,
                        ),
                    ],
                ),
            )
        ]


class SearchView(TemplateView):
    template_name = "peachjam_search/search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_placeholder_text = _("Search %(app_name)s") % {
            "app_name": settings.PEACHJAM["APP_NAME"]
        }
        context["labels"] = {
            "author": Author.model_label,
            "registry": CourtRegistry.model_label,
            "judge": Judge.model_label_plural,
            "searchPlaceholder": search_placeholder_text,
            "documentLabels": LabelSerializer(Label.objects.all(), many=True).data,
        }
        context["show_jurisdiction"] = settings.PEACHJAM["SEARCH_JURISDICTION_FILTER"]
        return context


class DocumentSearchViewSet(BaseDocumentViewSet):
    """API endpoint that allows document to be searched."""

    # This identifies the search configuration, for tracking changes across versions.
    # If a search setting changes, such as a boost or a new field, then changes this to the date of the release.
    config_version = "2024-05-01"

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
        MainSearchBackend,
        # overrides the fields that are fetched from ES
        SourceBackend,
        HighlightBackend,
    ]

    pagination_class = CustomPageNumberPagination

    # allowed and default ordering
    ordering_fields = {"date": "date", "title": "title"}
    ordering = ("_score", "date")
    # this means that at least 70% of terms must appear in ANY of the searched fields
    simple_query_string_options = {
        "default_operator": "OR",
        "minimum_should_match": "70%",
    }
    # how to treat queries for advanced search: AND
    advanced_simple_query_string_options = {
        "default_operator": "AND",
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
        "outcome": "outcome",
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
        "outcome": {"field": "outcome", "options": {"size": 100}},
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
    source = {"excludes": ["pages", "content", "flynote", "case_summary", "provisions"]}

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
            "outcome",
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

        trace = self.save_search_trace(resp)

        # show debug information to this user?
        resp.data["can_debug"] = self.request.user.has_perm("peachjam.can_debug_search")
        resp.data["trace_id"] = trace.id if trace else None

        return resp

    def save_search_trace(self, response):
        field_searches = {
            fld: self.request.GET.get(f"search__{fld}")
            for fld in self.search_fields.keys()
            if f"search__{fld}" in self.request.GET
        }

        filters = {
            fld: self.request.GET.getlist(fld)
            for fld in self.filter_fields.keys()
            if fld in self.request.GET
        }

        previous = None
        if self.request.GET.get("previous"):
            try:
                previous = SearchTrace.objects.filter(
                    pk=self.request.GET["previous"]
                ).first()
            except ValidationError:
                # ignore badly formed previous search ids
                pass

        search = self.request.GET.get("search", "")[:2048]
        # ignore nulls
        search = search.replace("\00", " ")

        # save the search trace
        return SearchTrace.objects.create(
            user=self.request.user if self.request.user.is_authenticated else None,
            config_version=self.config_version,
            request_id=self.request.id if self.request.id != "none" else None,
            search=search,
            field_searches=field_searches,
            n_results=response.data["count"],
            page=self.paginator.page.number,
            filters=filters,
            ordering=self.request.GET.get("ordering"),
            previous_search=previous,
            ip_address=self.request.headers.get("x-forwarded-for"),
            user_agent=self.request.headers.get("user-agent"),
        )

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


class SearchClickViewSet(CreateModelMixin, GenericViewSet):
    permission_classes = (AllowAny,)
    serializer_class = SearchClickSerializer
