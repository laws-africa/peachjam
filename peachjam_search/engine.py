import logging
from copy import deepcopy
from dataclasses import replace
from typing import Any, List, Optional, Self

from django.conf import settings
from elasticsearch_dsl import Search, TermsFacet
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl.query import Bool, MatchAll, MatchPhrase, Q, SimpleQueryString
from pydantic import BaseModel

from peachjam_search.documents import MultiLanguageIndexManager, SearchableDocument
from peachjam_search.profiles import SearchProfile
from peachjam_search.search_pipeline import (
    QueryAnalyser,
    QueryAnalysis,
    SearchPlan,
    SearchPlanner,
    SearchQuery,
)

log = logging.getLogger(__name__)


class ElasticsearchSearchCompiler:
    document = SearchableDocument
    index = None

    advanced_only_search_fields = {
        "case_number": None,
        "case_name": None,
        "judges_text": None,
    }

    # search configuration
    default_page_size = 10
    default_facets = [
        "nature",
        "publication",
        "sub_publication",
        "court",
        "year",
        "registry",
        "locality",
        "outcome",
        "judges",
        "authors",
        "language",
        "labels",
        "attorneys",
        "matter_type",
    ]
    # this should be enough for up to 5 pages, 10 per page with 3 chunks each
    knn_k = 5 * default_page_size * 3
    # number of candidates to find on each shard
    knn_num_candidates = knn_k * 10
    knn_embedding_field = "content_chunks.text_embedding"
    # https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html#knn-similarity-search  # noqa: E501
    # minimum cosine similarity (ranges from -1 to 1)
    # work backwards from score in [0, 1] and use
    #   similarity = 2 * score - 1
    # eg: 2 * 0.6 - 1 = 0.2
    knn_similarity = 0.4
    # ES clamps this at knn_k in any case
    rrf_rank_window_size = knn_k
    rrf_rank_constant = 60

    default_source = {
        "includes": [
            "expression_frbr_uri",
            "date",
            "nature",
            "doc_type",
            "title",
            "jurisdiction",
            "locality",
            "citation",
            "authors",
            "labels",
            "alternative_names",
            "flynote",
            "blurb",
            "court",
            "matter_type",
            "publication",
            "sub_publication",
        ]
    }

    default_highlight = {
        "title": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 0,
            "number_of_fragments": 0,
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
        },
        "alternative_names": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 0,
            "number_of_fragments": 0,
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
        },
        "citation": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 0,
            "number_of_fragments": 0,
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
        },
        "content": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 80,
            "number_of_fragments": 2,
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
        },
    }

    # allowed filter fields
    filter_fields = {
        "authors",
        "court",
        "date",
        "created_at",
        "doc_type",
        "jurisdiction",
        "language",
        "locality",
        "matter_type",
        "nature",
        "publication",
        "sub_publication",
        "year",
        "judges",
        "registry",
        "division",
        "attorneys",
        "outcome",
        "case_action",
        "labels",
    }

    # these support ranges
    range_filter_fields = {
        "date",
        "created_at",
    }

    facet_fields = [
        {"field": "doc_type", "options": {"size": 100}},
        {
            "field": "authors",
            "options": {"size": 100},
        },
        {
            "field": "jurisdiction",
            "options": {"size": 100},
        },
        {
            "field": "locality",
            "options": {"size": 100},
        },
        {
            "field": "matter_type",
            "options": {"size": 100},
        },
        {"field": "year", "options": {"size": 100}},
        {
            "field": "nature",
            "options": {"size": 100},
        },
        {
            "field": "publication",
            "options": {"size": 100},
        },
        {
            "field": "sub_publication",
            "options": {"size": 100},
        },
        {
            "field": "language",
            "options": {"size": 100},
        },
        {"field": "court", "options": {"size": 100}},
        {"field": "judges", "options": {"size": 100}},
        {"field": "registry", "options": {"size": 100}},
        {"field": "division", "options": {"size": 100}},
        {"field": "attorneys", "options": {"size": 100}},
        {"field": "outcome", "options": {"size": 100}},
        {"field": "case_action", "options": {"size": 100}},
        {"field": "labels", "options": {"size": 100}},
    ]

    pages_inner_hits = {
        "_source": ["pages.page_num"],
        "highlight": {
            "fields": {"pages.body": {}, "pages.body.exact": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 80,
            "number_of_fragments": 2,
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
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
            "max_analyzed_offset": settings.ELASTICSEARCH_MAX_ANALYZED_OFFSET,
        },
    }

    search_query: SearchQuery | None = None
    plan: SearchPlan | None = None

    def __init__(self) -> None:
        self.client = connections.get_connection(self.document._get_using())
        self.index = (
            MultiLanguageIndexManager.get_instance().get_all_search_index_names()
        )

    @property
    def profile(self) -> SearchProfile:
        """The profile selected by the plan being compiled."""
        return self.plan.profile

    @staticmethod
    def build_search_fields(profile: SearchProfile) -> dict[str, dict[str, Any] | None]:
        """Translate profile boosts into compiler field definitions."""
        return {
            field_name: (
                None if boost is None or float(boost) == 1.0 else {"boost": boost}
            )
            for field_name, boost in profile.search_field_boosts.items()
        }

    @classmethod
    def build_advanced_search_fields(
        cls, profile: SearchProfile
    ) -> dict[str, dict[str, Any] | None]:
        """Add fixed advanced-only fields to the profile-driven fields."""
        fields = dict(cls.advanced_only_search_fields)
        fields.update(cls.build_search_fields(profile))
        return fields

    @classmethod
    def advanced_search_field_names(cls) -> list[str]:
        """Return the advanced form fields accepted by the default compiler."""
        return list(cls.build_advanced_search_fields(SearchProfile.default()))

    def suggest(self, query: str) -> Any:
        search = Search(using=self.client, index=self.index)
        search = search.source(["_id"]).suggest(
            "prefix",
            query,
            completion={
                "field": "suggest",
                "size": 5,
                "skip_duplicates": True,
            },
        )
        return search.execute()

    def compile(self, search_query: SearchQuery, plan: SearchPlan) -> "RetrieverSearch":
        """Compile one query and plan into an Elasticsearch request."""
        self.search_query = search_query
        self.plan = plan
        return self.build_search()

    def build_search(self) -> "RetrieverSearch":
        search = self.create_search()
        search = self.add_query_from_plan(search)
        search = self.add_filters(search)
        search = self.add_sort(search)
        search = self.add_paging(search)
        search = self.add_source(search)
        search = self.add_highlight(search)
        search = self.add_aggs(search)
        search = self.add_extra(search)
        return self.add_retrievers(search)

    def create_search(self) -> "RetrieverSearch":
        return RetrieverSearch(using=self.client, index=self.index)

    def add_source(self, search: "RetrieverSearch") -> "RetrieverSearch":
        return search.source(self.search_query.source or self.default_source)

    def add_filters(self, search: "RetrieverSearch") -> "RetrieverSearch":
        # always applied
        search = search.filter("term", is_most_recent=True)
        facetable_fields = {facet["field"] for facet in self.facet_fields}

        for field, values in self.search_query.filters.items():
            # if this field is faceted, then apply it as a post-filter
            if field in facetable_fields:
                search = search.post_filter("terms", **{field: values})
            elif field in self.range_filter_fields:
                # range fields (can't be faceted)
                start, end = values
                values = {}
                if start:
                    values["gte"] = start
                if end:
                    values["lte"] = end
                search = search.filter("range", **{field: values})
            else:
                # normal filter field
                search = search.filter("terms", **{field: values})

        return search

    def add_aggs(self, search: "RetrieverSearch") -> "RetrieverSearch":
        if not self.search_query.facets:
            return search

        aggs = self.build_aggs()

        filters = {}
        for field, values in self.search_query.filters.items():
            filters[field] = Q("terms", **{field: values})

        for agg_field, facet in aggs.items():
            agg = facet.get_aggregation()
            agg_filter = MatchAll()
            for field, filter in filters.items():
                # apply filters that are applicable for facets other than this one
                if agg_field == field or field not in self.search_query.facets:
                    continue
                agg_filter &= filter

            search.aggs.bucket(
                f"_filter_{agg_field}", "filter", filter=agg_filter
            ).bucket(agg_field, agg)

        return search

    def add_highlight(self, search: "RetrieverSearch") -> "RetrieverSearch":
        highlight = self.search_query.highlight or self.default_highlight
        for field, options in highlight.items():
            search = search.highlight(field, **options)
        return search

    def add_sort(self, search: "RetrieverSearch") -> "RetrieverSearch":
        if self.search_query.ordering == "-score":
            return search.sort("_score")
        return search.sort(self.search_query.ordering)

    def add_paging(self, search: "RetrieverSearch") -> "RetrieverSearch":
        # TODO: guard against going beyond end of results
        return search[
            (self.search_query.page - 1)
            * self.search_query.page_size : self.search_query.page
            * self.search_query.page_size
        ]

    def expand_retriever_window_to_page(self) -> None:
        """Ensure hybrid retrievers can return the full requested page."""
        if self.plan is not None and self.plan.mode == "hybrid":
            self.rrf_rank_window_size = max(
                self.rrf_rank_window_size,
                self.search_query.page * self.search_query.page_size,
            )

    def add_extra(self, search: "RetrieverSearch") -> "RetrieverSearch":
        return search.extra(explain=self.search_query.explain)

    def add_query_from_plan(self, search: "RetrieverSearch") -> "RetrieverSearch":
        """Compile the retrieval and ranking clauses selected by the plan."""
        must_queries = []
        should_queries = []

        # pagerank etc.
        must_queries.extend(self.build_rank_feature_queries())

        clause_names = {clause.name for clause in self.plan.retrieval_clauses}

        if "advanced_per_field" in clause_names:
            must_queries.extend(self.build_per_field_queries())
        if "advanced_all" in clause_names:
            must_queries.extend(self.build_advanced_all_queries())
        if "advanced_content" in clause_names:
            must_queries.extend(self.build_advanced_content_queries())
        if "basic" in clause_names:
            should_queries.extend(self.build_basic_queries())
        if "content_phrase" in clause_names:
            should_queries.extend(self.build_content_phrase_queries())
        if "nested_pages" in clause_names:
            should_queries.extend(self.build_nested_page_queries())
        if "nested_provisions" in clause_names:
            should_queries.extend(self.build_nested_provision_queries())

        return search.query(
            "bool",
            must=must_queries,
            should=should_queries,
            minimum_should_match=1 if should_queries else 0,
        )

    def add_retrievers(self, search: "RetrieverSearch") -> "RetrieverSearch":
        if self.plan.mode == "text":
            return search

        knn_query = self.build_knn_query(search, self.plan.mode)
        if self.plan.mode == "semantic":
            # we don't need a retriever, just a normal knn-based query
            return search.query(knn_query)

        # hybrid
        standard_query = search.to_dict()
        for attr in list(standard_query.keys()):
            if attr not in ["query", "filter"]:
                del standard_query[attr]

        standard_query["_name"] = "text"
        knn_query["_name"] = "semantic"

        # TODO: elasticsearch 8 client supports this directly
        search.retriever = {
            "rrf": {
                "rank_window_size": self.rrf_rank_window_size,
                "rank_constant": self.rrf_rank_constant,
                "retrievers": [
                    {"standard": standard_query},
                    {"standard": knn_query},
                ],
            }
        }

        return search

    def build_rank_feature_queries(self, factor: float = 1.0) -> list[Any]:
        """Compile the plan's resolved rank-feature signals."""
        queries = []
        for signal in self.plan.ranking_signals:
            if not signal.boost:
                continue
            kwargs = {
                "field": signal.field,
                "boost": signal.boost * factor,
            }
            if signal.saturation_pivot:
                kwargs["saturation"] = {"pivot": signal.saturation_pivot}
            queries.append(Q("rank_feature", **kwargs))
        return queries

    def build_per_field_queries(self) -> list[Any]:
        """Supports searching across multiple fields. Specify zero or more query parameters such as search__title=foo"""
        queries = []

        profile = self.profile
        for field in self.build_advanced_search_fields(profile):
            if field == "content":
                # advanced search on the "content" field (which must include pages and provisions too), is handled
                # by build_advanced_content_queries
                continue
            query = self.search_query.field_queries.get(field)
            if query:
                queries.append(
                    SimpleQueryString(
                        query=query,
                        fields=[self.get_field(field)],
                        **profile.advanced_simple_query_string_options,
                    )
                )

        return queries

    def is_advanced_search(self) -> bool:
        """It's an advanced search if any of the search__* query parameters are present."""
        return self.search_query.is_advanced

    def build_basic_queries(self) -> list[Any]:
        """This implements a simple_query_string query across multiple fields, using AND logic for the terms
        in a field, but effectively OR (should) logic between the fields."""
        query = self.search_query.query
        if not query:
            return []

        profile = self.profile
        search_fields = self.build_search_fields(profile)
        query_fields = [self.get_field(field) for field in search_fields]
        queries = [
            SimpleQueryString(
                query=query,
                fields=[field],
                **profile.simple_query_string_options,
            )
            for field in query_fields
        ]

        if " " in query:
            # do optimistic match-phrase queries for multi-word queries
            for field, options in search_fields.items():
                phrase_query = {"query": query, "slop": profile.phrase_match_slop}
                if "boost" in (options or {}):
                    phrase_query["boost"] = options["boost"]
                if field == "content":
                    phrase_query["boost"] = profile.phrase_match_content_boost
                queries.append(MatchPhrase(**{field: phrase_query}))

        return queries

    def build_content_phrase_queries(self) -> list[Any]:
        """Adds a best-effort phrase match query on the content field."""
        if not self.search_query.query:
            return []

        return [
            MatchPhrase(
                content={
                    "query": self.search_query.query,
                    "slop": self.profile.phrase_match_slop,
                    "boost": self.profile.phrase_match_content_boost,
                }
            )
        ]

    def build_nested_page_queries(self) -> list[Any]:
        """Does a nested page search, and includes highlights."""
        if not self.search_query.query:
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
                            query=self.search_query.query,
                            fields=["pages.body"],
                            quote_field_suffix=".exact",
                            **self.profile.simple_query_string_options,
                        )
                    ],
                    should=[
                        MatchPhrase(
                            pages__body={
                                "query": self.search_query.query,
                                "slop": self.profile.phrase_match_slop,
                                "boost": self.profile.phrase_match_content_boost,
                            }
                        ),
                    ],
                ),
            )
        ]

    def build_nested_provision_queries(self) -> list[Any]:
        """Does a nested provision search, and includes highlights."""
        if not self.search_query.query:
            return []

        return [
            Q(
                "nested",
                path="provisions",
                inner_hits=self.provisions_inner_hits,
                query=Q(
                    "bool",
                    should=[
                        MatchPhrase(
                            provisions__body={
                                "query": self.search_query.query,
                                "slop": self.profile.phrase_match_slop,
                                "boost": self.profile.phrase_match_content_boost,
                            }
                        ),
                        SimpleQueryString(
                            query=self.search_query.query,
                            fields=["provisions.body"],
                            quote_field_suffix=".exact",
                            **self.profile.simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.search_query.query,
                            fields=[
                                self.get_boosted_field(
                                    "provisions.title",
                                    self.profile.provision_title_boost,
                                ),
                                self.get_boosted_field(
                                    "provisions.parent_titles",
                                    self.profile.provision_parent_titles_boost,
                                ),
                            ],
                            **self.profile.simple_query_string_options,
                        ),
                    ],
                ),
            )
        ]

    def build_advanced_all_queries(self) -> list[Any]:
        """Build queries for search__all (advanced search across all fields). Similar logic to build_basic_queries,
        but all terms are required by default."""
        query = self.search_query.field_queries.get("all")
        if not query:
            return []

        profile = self.profile
        query_fields = [
            self.get_field(field)
            for field in self.build_advanced_search_fields(profile)
        ]
        return [
            Q(
                "bool",
                minimum_should_match=1,
                should=[
                    SimpleQueryString(
                        query=query,
                        fields=[field],
                        **profile.advanced_simple_query_string_options,
                    )
                    for field in query_fields
                ]
                + self.build_advanced_content_query(query),
            )
        ]

    def build_advanced_content_queries(self) -> list[Any]:
        """Adds advanced search queries for search__content, which searches across content, pages.body and
        provisions.body."""
        query = self.search_query.field_queries.get("content")

        # don't allow search__content and search__all to clash, only one is needed to search content fields
        if query and self.search_query.field_queries.get("all"):
            return []

        if query:
            return [
                Q(
                    "bool",
                    minimum_should_match=1,
                    should=self.build_advanced_content_query(query),
                )
            ]
        return []

    def build_advanced_content_query(self, query: str) -> list[Any]:
        # TODO: negative queries don't work, because they must be applied to the whole content, not just a
        # particular page or provision
        return [
            # content
            SimpleQueryString(
                query=query,
                fields=["content"],
                **self.profile.advanced_simple_query_string_options,
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
                    **self.profile.advanced_simple_query_string_options,
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
                            **self.profile.advanced_simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.search_query.query,
                            fields=[
                                self.get_boosted_field(
                                    "provisions.title",
                                    self.profile.provision_title_boost,
                                ),
                                self.get_boosted_field(
                                    "provisions.parent_titles",
                                    self.profile.provision_parent_titles_boost,
                                ),
                            ],
                            **self.profile.advanced_simple_query_string_options,
                        ),
                    ],
                ),
            ),
        ]

    def build_aggs(self) -> dict[str, Any]:
        aggs = {}
        for field in self.facet_fields:
            facet = field.get("facet", TermsFacet)
            aggs[field["field"]] = facet(field=field["field"], **field["options"])
        return aggs

    def build_knn_query(self, search: "RetrieverSearch", mode: str) -> dict[str, Any]:
        """Builds a KNN query."""
        must_queries = [q.to_dict() for q in self.build_rank_feature_queries(0.1)]
        must_queries.append(
            {
                "nested": {
                    "path": "content_chunks",
                    "inner_hits": {
                        "_source": {
                            "excludes": ["content_chunks.text_embedding"],
                        }
                    },
                    "score_mode": "max",
                    "query": {
                        "knn": {
                            "field": self.knn_embedding_field,
                            "k": self.knn_k,
                            "num_candidates": self.knn_num_candidates,
                            "similarity": self.knn_similarity,
                            "query_vector": self.get_query_embedding(
                                self.search_query.query
                            ),
                        }
                    },
                }
            }
        )

        knn = {"bool": {"must": must_queries}}

        if mode == "semantic":
            return knn

        # hybrid mode needs the filters from the original search
        search_dict = search.to_dict()
        knn = {
            "query": knn,
        }
        if "filter" in search_dict["query"]["bool"]:
            knn["filter"] = search_dict["query"]["bool"]["filter"]

        return knn

    def get_query_embedding(self, query: str | None) -> list[float]:
        from peachjam_ml.embeddings import get_query_embedding

        return get_query_embedding(query)

    def get_field(self, field: str) -> str:
        profile = self.profile
        options = (
            self.build_search_fields(profile).get(field, {})
            or self.build_advanced_search_fields(profile).get(field, {})
            or {}
        )
        if "boost" in options:
            return self.get_boosted_field(field, options["boost"])
        return field

    def get_boosted_field(self, field: str, boost: float | int | None) -> str:
        if boost is None or float(boost) == 1.0:
            return field
        boost = float(boost)
        boost_value = int(boost) if boost.is_integer() else boost
        return f"{field}^{boost_value}"

    def execute(self) -> Any:
        """Execute a directly compiled search.

        Portion search remains intentionally lower-level for now, so it uses
        the compiler directly rather than the document-search pipeline.
        """
        response = self.build_search().execute()
        if response._shards.failed:
            log.error(f"ES query failed: {response._shards.failures}")
            if settings.ELASTICSEARCH_FAIL_ON_SHARD_FAILURE:
                raise Exception(f"ES query failed: {response._shards.failures}")
        return response

    def get_debug_inputs(self) -> dict[str, Any]:
        return {
            "query": self.search_query.query,
            "field_queries": self.search_query.field_queries,
            "filters": self.search_query.filters,
            "mode": self.plan.mode,
            "page": self.search_query.page,
            "page_size": self.search_query.page_size,
            "ordering": self.search_query.ordering,
        }

    def build_debug_payload(self) -> dict[str, Any]:
        search = self.build_search()
        query = search.to_dict()
        return {
            "index": self.index,
            "mode": self.plan.mode,
            "inputs": self.get_debug_inputs(),
            "query": query,
            "redacted_query": self.redact_debug_query(query),
        }

    @classmethod
    def redact_debug_query(cls, value: Any) -> Any:
        value = deepcopy(value)

        def redact(item):
            if isinstance(item, dict):
                return {
                    key: (
                        "[embedding vector omitted]"
                        if key == "query_vector" or key.endswith("_embedding")
                        else redact(child)
                    )
                    for key, child in item.items()
                }
            if isinstance(item, list):
                if item and all(isinstance(x, (int, float)) for x in item):
                    return "[embedding vector omitted]"
                return [redact(child) for child in item]
            return item

        return redact(value)


class SearchEngine:
    """One-shot document-search orchestration.

    Inputs, analysis and plan are deliberately explicit instance data.  The
    compiler owns Elasticsearch details and receives a complete plan.
    """

    document = SearchableDocument

    def __init__(
        self,
        search_query: SearchQuery | None = None,
        analyser: QueryAnalyser | None = None,
        planner: SearchPlanner | None = None,
        compiler: ElasticsearchSearchCompiler | None = None,
    ) -> None:
        # ``None`` is retained only for utility callers such as suggestions.
        # Document searches should always be constructed with a SearchQuery.
        self.search_query = search_query or SearchQuery(
            query=None,
            field_queries={},
            mode="text",
            filters={},
            facets=[],
            page=1,
            page_size=10,
            ordering="-score",
            explain=False,
        )
        self.analyser = analyser or QueryAnalyser()
        self.planner = planner or SearchPlanner()
        self.compiler = compiler or ElasticsearchSearchCompiler()
        self.analysis: QueryAnalysis | None = None
        self.plan: SearchPlan | None = None
        self.compiled_search: RetrieverSearch | None = None

    def set_search_query(self, search_query: SearchQuery) -> Self:
        """Replace the caller input and discard derived pipeline state."""
        self.search_query = search_query
        self.analysis = None
        self.plan = None
        self.compiled_search = None
        return self

    def _replace_search_query(self, **changes: Any) -> Self:
        return self.set_search_query(replace(self.search_query, **changes))

    @property
    def query(self):
        return self.search_query.query

    @query.setter
    def query(self, value):
        self._replace_search_query(query=value)

    @property
    def field_queries(self):
        return self.search_query.field_queries

    @field_queries.setter
    def field_queries(self, value):
        self._replace_search_query(field_queries=value)

    @property
    def filters(self):
        return self.search_query.filters

    @filters.setter
    def filters(self, value):
        self._replace_search_query(filters=value)

    @property
    def page(self):
        return self.search_query.page

    @page.setter
    def page(self, value):
        self._replace_search_query(page=value)

    @property
    def page_size(self):
        return self.search_query.page_size

    @page_size.setter
    def page_size(self, value):
        self._replace_search_query(page_size=value)

    @property
    def mode(self):
        return self.search_query.mode

    @mode.setter
    def mode(self, value):
        self._replace_search_query(mode=value)

    @property
    def ordering(self):
        return self.search_query.ordering

    @ordering.setter
    def ordering(self, value):
        self._replace_search_query(ordering=value)

    @property
    def explain(self):
        return self.search_query.explain

    @explain.setter
    def explain(self, value):
        self._replace_search_query(explain=value)

    @property
    def facets(self):
        return self.search_query.facets

    @facets.setter
    def facets(self, value):
        self._replace_search_query(facets=value)

    @property
    def index(self):
        return self.compiler.index

    @index.setter
    def index(self, value):
        self.compiler.index = value

    @property
    def client(self):
        return self.compiler.client

    @property
    def source(self):
        return self.search_query.source

    @source.setter
    def source(self, value):
        self._replace_search_query(source=value)

    @property
    def highlight(self):
        return self.search_query.highlight

    @highlight.setter
    def highlight(self, value):
        self._replace_search_query(highlight=value)

    def execute(self) -> Any:
        """The main entry-point for running the search in search_query. This analysis the search, builds a search
        plan, compiles it to an Elasticsearch query, and executes it."""
        self.build_search()
        return self.execute_search()

    def build_search(self) -> "RetrieverSearch":
        """Analyse, plan and compile the search query into an Elasticsearch query."""
        self.analyse()
        self.build_plan()
        return self.compile()

    def analyse(self) -> QueryAnalysis:
        if self.analysis is None:
            if self.search_query.is_advanced:
                self.analysis = QueryAnalysis(
                    raw_query=self.search_query.query or "",
                    clean_query=self.search_query.query or "",
                )
            else:
                self.analysis = self.analyser.analyse(self.search_query.query or "")
        return self.analysis

    def build_plan(self) -> SearchPlan:
        if self.plan is None:
            self.plan = self.planner.build(self.search_query, self.analyse())
        return self.plan

    def compile(self) -> "RetrieverSearch":
        if self.plan is None:
            self.build_plan()
        self.compiled_search = self.compiler.compile(self.search_query, self.plan)
        return self.compiled_search

    def execute_search(self) -> Any:
        response = self.compiled_search.execute()
        if response._shards.failed:
            log.error(f"ES query failed: {response._shards.failures}")
            if settings.ELASTICSEARCH_FAIL_ON_SHARD_FAILURE:
                raise Exception(f"ES query failed: {response._shards.failures}")
        return response

    def expand_retriever_window_to_page(self) -> None:
        if self.search_query.mode == "hybrid":
            self.compiler.rrf_rank_window_size = max(
                self.compiler.rrf_rank_window_size,
                self.search_query.page * self.search_query.page_size,
            )

    def suggest(self, query: str) -> Any:
        return self.compiler.suggest(query)

    def build_debug_payload(self) -> dict[str, Any]:
        search = self.build_search()
        query = search.to_dict()
        return {
            "index": self.index,
            "mode": self.search_query.mode,
            "inputs": {
                "query": self.search_query.query,
                "field_queries": self.search_query.field_queries,
                "filters": self.search_query.filters,
                "facets": self.search_query.facets,
                "page": self.search_query.page,
                "page_size": self.search_query.page_size,
                "ordering": self.search_query.ordering,
                "explain": self.search_query.explain,
                "source": self.search_query.source,
                "highlight": self.search_query.highlight,
            },
            "query": query,
            "redacted_query": self.redact_debug_query(query),
            "analysis": self.analysis.to_dict(),
            "plan": self.plan.to_dict(),
        }

    redact_debug_query = ElasticsearchSearchCompiler.redact_debug_query


class PortionSearchFilters(BaseModel):
    work_frbr_uri: Optional[str] = None
    work_frbr_uri__in: Optional[List[str]] = None
    expression_frbr_uri: Optional[str] = None
    expression_frbr_uri__in: Optional[List[str]] = None
    frbr_place: Optional[str] = None
    frbr_place__in: Optional[List[str]] = None
    frbr_doctype: Optional[str] = None
    frbr_doctype__in: Optional[List[str]] = None
    frbr_subtype: Optional[str] = None
    frbr_subtype__in: Optional[List[str]] = None
    repealed: Optional[bool] = None
    commenced: Optional[bool] = None
    principal: Optional[bool] = None

    def to_es_query(self):
        must = []
        for key, value in self.model_dump(exclude_none=True).items():
            field, *lookup = key.split("__")
            lookup = lookup[0] if lookup else "exact"

            if field.startswith("frbr_"):
                # ES fields are named with frbr_uri_...
                field = "frbr_uri_" + field[5:]

            if lookup == "exact":
                must.append({"term": {field: value}})
            elif lookup == "in":
                must.append({"terms": {field: value}})
            else:
                raise ValueError(f"Unsupported lookup: {lookup}")
        return must


class PortionSearchEngine(ElasticsearchSearchCompiler):
    """A SearchEngine designed for hybrid search returning portions of documents, rather than documents. Useful
    for RAG.
    """

    default_source = [
        "title",
        "expression_frbr_uri",
        "frbr_uri_subtype",
        "frbr_uri_actor",
        "repealed",
        "commenced",
        "principal",
        "flynote",
        "blurb",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.query: str | None = None
        self.filters: list[PortionSearchFilters] = []
        self.mode = "text"

    def build_search(self) -> "RetrieverSearch":
        """Build the legacy portion search using a transient document plan.

        Portion search has its own input shape and filters, but shares the
        document retrieval and semantic-query compilation helpers. Supplying a
        concrete query and plan here keeps those helpers free of compatibility
        accessors.
        """
        # number of candidates to find on each shard
        self.knn_num_candidates = self.knn_k * 10
        self.search_query = SearchQuery(
            query=self.query,
            field_queries={},
            mode=self.mode,
            filters={},
            facets=[],
            page=1,
            page_size=self.default_page_size,
            ordering="-score",
            explain=False,
            source=self.default_source,
            highlight={},
        )
        self.plan = SearchPlanner().build(
            self.search_query,
            QueryAnalysis(raw_query=self.query or "", clean_query=self.query),
        )

        search = RetrieverSearch(using=self.client, index=self.index)
        search = self.add_source(search)
        search = self.add_query_from_plan(search)
        search = self.add_sort(search)
        search = self.add_filters(search)
        search = self.add_retrievers(search)
        return search

    def get_debug_inputs(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "filters": [
                (
                    f.model_dump(exclude_none=True)
                    if hasattr(f, "model_dump")
                    else f.dict(exclude_none=True)
                )
                for f in self.filters
            ],
            "mode": self.mode,
            "knn_k": self.knn_k,
            "knn_num_candidates": self.knn_num_candidates,
        }

    def add_filters(self, search: "RetrieverSearch") -> "RetrieverSearch":
        search = search.filter("term", is_most_recent=True)

        for f in self.filters:
            search = search.query(Bool(filter=f.to_es_query()))

        return search


class RetrieverSearch(Search):
    retriever = None

    def to_dict(self, count=False, **kwargs):
        d = super().to_dict(count, **kwargs)

        if self.retriever:
            del d["query"]
            # TODO: cannot specify [retriever] and [sort];'
            if "sort" in d:
                del d["sort"]
            d["retriever"] = self.retriever

        return d

    def _clone(self):
        s = super()._clone()
        s.retriever = self.retriever
        return s
