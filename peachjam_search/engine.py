import logging

from django.conf import settings
from elasticsearch_dsl import Search, TermsFacet
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl.query import MatchAll, MatchPhrase, Q, SimpleQueryString

from peachjam.models import pj_settings
from peachjam_search.documents import MultiLanguageIndexManager, SearchableDocument
from peachjam_search.embeddings import get_query_embedding

log = logging.getLogger(__name__)


class SearchEngine:
    document = SearchableDocument
    index = None

    # query details that can be passed in by the client
    query = None
    field_queries = None
    page = 1
    ordering = "-score"
    explain = False
    # dict from field name to list of values
    filters = None
    facets = [
        "nature",
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
    # text / semantic / hybrid
    mode = "text"

    # search configuration
    page_size = 10
    # this should be enough for up to 5 pages, 10 per page with 3 chunks each
    knn_k = 5 * page_size * 3
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

    source = {
        "excludes": [
            "pages",
            "content",
            "content_chunks",
            "flynote",
            "case_summary",
            "provisions",
            "suggest",
        ]
    }

    highlight = {
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

    search_fields = {
        "title": {"boost": 8},
        "title_expanded": {"boost": 3},
        "citation": {"boost": 2},
        "alternative_names": {"boost": 4},
        "content": None,
    }

    advanced_search_fields = {
        "case_number": None,
        "case_name": None,
        "judges_text": None,
    }
    advanced_search_fields.update(search_fields)

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
        "year",
        "judges",
        "registry",
        "attorneys",
        "outcome",
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
            "field": "language",
            "options": {"size": 100},
        },
        {"field": "court", "options": {"size": 100}},
        {"field": "judges", "options": {"size": 100}},
        {"field": "registry", "options": {"size": 100}},
        {"field": "attorneys", "options": {"size": 100}},
        {"field": "outcome", "options": {"size": 100}},
        {"field": "labels", "options": {"size": 100}},
    ]

    # when doing a SHOULD phrase match on content fields, what should we boost by?
    optimistic_phrase_match_content_boost = 4
    optimistic_phrase_match_slop = 0

    # this means that at least 70% of terms must appear in ANY of the searched fields
    simple_query_string_options = {
        "default_operator": "OR",
        # all for 1-4 terms, 5 or more requires at 80% to match
        "minimum_should_match": "4<80%",
    }

    # how to treat queries for advanced search: AND
    advanced_simple_query_string_options = {
        "default_operator": "AND",
    }

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

    def __init__(self):
        self.client = connections.get_connection(self.document._get_using())
        self.index = (
            MultiLanguageIndexManager.get_instance().get_all_search_index_names()
        )
        self.field_queries = {}
        self.filters = {}

    def execute(self):
        search = self.build_search()
        response = search.execute()

        if response._shards.failed:
            # it's better to fail here than to silently return partial (or no) results
            log.error(f"ES query failed: {response._shards.failures}")
            if settings.ELASTICSEARCH_FAIL_ON_SHARD_FAILURE:
                raise Exception(f"ES query failed: {response._shards.failures}")

        return response

    def suggest(self, query):
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

    def build_search(self):
        search = RetrieverSearch(using=self.client, index=self.index)
        search = self.add_query(search)
        search = self.add_filters(search)
        search = self.add_sort(search)
        search = self.add_paging(search)
        search = self.add_source(search)
        search = self.add_highlight(search)
        search = self.add_aggs(search)
        search = self.add_extra(search)
        search = self.add_retrievers(search)
        return search

    def add_source(self, search):
        return search.source(self.source)

    def add_filters(self, search):
        # always applied
        search = search.filter("term", is_most_recent=True)

        for field, values in self.filters.items():
            # if this field is faceted, then apply it as a post-filter
            if field in self.facets:
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

    def add_aggs(self, search):
        aggs = self.build_aggs()

        filters = {}
        for field, values in self.filters.items():
            filters[field] = Q("terms", **{field: values})

        for agg_field, facet in aggs.items():
            agg = facet.get_aggregation()
            agg_filter = MatchAll()
            for field, filter in filters.items():
                # apply filters that are applicable for facets other than this one
                if agg_field == field or field not in self.facets:
                    continue
                agg_filter &= filter

            search.aggs.bucket(
                f"_filter_{agg_field}", "filter", filter=agg_filter
            ).bucket(agg_field, agg)

        return search

    def add_highlight(self, search):
        for field, options in self.highlight.items():
            search = search.highlight(field, **options)
        return search

    def add_sort(self, search):
        if self.ordering == "-score":
            return search.sort("_score")
        return search.sort(self.ordering)

    def add_paging(self, search):
        # TODO: guard against going beyond end of results
        return search[(self.page - 1) * self.page_size : self.page * self.page_size]

    def add_extra(self, search):
        return search.extra(explain=self.explain)

    def add_query(self, search):
        """Build the actual search queries."""
        must_queries = []
        should_queries = []

        if self.mode in ["text", "hybrid"]:
            must_queries.extend(self.build_rank_feature_queries())

        if self.is_advanced_search():
            # we only support text mode with advanced search
            self.mode = "text"

            # these handle advanced search, and can't be combined with normal search because they both
            # build queries to return nested content, and ES complains if multiple queries try to return the
            # same nested content fields
            must_queries.extend(self.build_per_field_queries())
            must_queries.extend(self.build_advanced_all_queries())
            must_queries.extend(self.build_advanced_content_queries())
        else:
            # these handle basic search
            if self.mode in ["text", "hybrid"]:
                should_queries.extend(self.build_basic_queries())
                should_queries.extend(self.build_content_phrase_queries())
                should_queries.extend(self.build_nested_page_queries())
                should_queries.extend(self.build_nested_provision_queries())

        return search.query(
            "bool",
            must=must_queries,
            should=should_queries,
            minimum_should_match=1 if should_queries else 0,
        )

    def add_retrievers(self, search):
        if self.mode == "text":
            return search

        knn_query = self.build_knn_query(search, self.mode)
        if self.mode == "semantic":
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

    def build_rank_feature_queries(self, factor=1.0):
        """Apply a rank_feature query to boost the score based on the ranking field."""
        if pj_settings().pagerank_boost_value:
            # apply pagerank boost to the score using the saturation function
            kwargs = {
                "field": "ranking",
                "boost": pj_settings().pagerank_boost_value * factor,
            }
            if pj_settings().pagerank_pivot_value:
                kwargs["saturation"] = {"pivot": pj_settings().pagerank_pivot_value}
            return [Q("rank_feature", **kwargs)]
        return []

    def build_per_field_queries(self):
        """Supports searching across multiple fields. Specify zero or more query parameters such as search__title=foo"""
        queries = []

        for field in self.advanced_search_fields.keys():
            if field == "content":
                # advanced search on the "content" field (which must include pages and provisions too), is handled
                # by build_advanced_content_queries
                continue
            query = self.field_queries.get(field)
            if query:
                queries.append(
                    SimpleQueryString(
                        query=query,
                        fields=[self.get_field(field)],
                        **self.advanced_simple_query_string_options,
                    )
                )

        return queries

    def is_advanced_search(self):
        """It's an advanced search if any of the search__* query parameters are present."""
        return any(
            self.field_queries.get(field)
            for field in list(self.advanced_search_fields.keys()) + ["all"]
        )

    def build_basic_queries(self):
        """This implements a simple_query_string query across multiple fields, using AND logic for the terms
        in a field, but effectively OR (should) logic between the fields."""
        if not self.query:
            return []

        query_fields = [
            self.get_field(field) for field, options in self.search_fields.items()
        ]
        queries = [
            SimpleQueryString(
                query=self.query,
                fields=[field],
                **self.simple_query_string_options,
            )
            for field in query_fields
        ]

        if " " in self.query:
            # do optimistic match-phrase queries for multi-word queries
            for field, options in self.search_fields.items():
                query = {"query": self.query, "slop": self.optimistic_phrase_match_slop}
                if "boost" in (options or {}):
                    query["boost"] = options["boost"]
                if field == "content":
                    query["boost"] = self.optimistic_phrase_match_content_boost
                queries.append(MatchPhrase(**{field: query}))

        return queries

    def build_content_phrase_queries(self):
        """Adds a best-effort phrase match query on the content field."""
        if not self.query:
            return []

        return [
            MatchPhrase(
                content={
                    "query": self.query,
                    "slop": self.optimistic_phrase_match_slop,
                    "boost": self.optimistic_phrase_match_content_boost,
                }
            )
        ]

    def build_nested_page_queries(self):
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
                            **self.simple_query_string_options,
                        )
                    ],
                    should=[
                        MatchPhrase(
                            pages__body={
                                "query": self.query,
                                "slop": self.optimistic_phrase_match_slop,
                                "boost": self.optimistic_phrase_match_content_boost,
                            }
                        ),
                    ],
                ),
            )
        ]

    def build_nested_provision_queries(self):
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
                        MatchPhrase(
                            provisions__body={
                                "query": self.query,
                                "slop": self.optimistic_phrase_match_slop,
                                "boost": self.optimistic_phrase_match_content_boost,
                            }
                        ),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.body"],
                            quote_field_suffix=".exact",
                            **self.simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.title^4", "provisions.parent_titles^2"],
                            **self.simple_query_string_options,
                        ),
                    ],
                ),
            )
        ]

    def build_advanced_all_queries(self):
        """Build queries for search__all (advanced search across all fields). Similar logic to build_basic_queries,
        but all terms are required by default."""
        query = self.field_queries.get("all")
        if not query:
            return []

        query_fields = [
            self.get_field(field)
            for field, options in self.advanced_search_fields.items()
        ]
        return [
            Q(
                "bool",
                minimum_should_match=1,
                should=[
                    SimpleQueryString(
                        query=query,
                        fields=[field],
                        **self.advanced_simple_query_string_options,
                    )
                    for field in query_fields
                ]
                + self.build_advanced_content_query(query),
            )
        ]

    def build_advanced_content_queries(self):
        """Adds advanced search queries for search__content, which searches across content, pages.body and
        provisions.body."""
        query = self.field_queries.get("content")

        # don't allow search__content and search__all to clash, only one is needed to search content fields
        if query and self.field_queries.get("all"):
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

    def build_advanced_content_query(self, query):
        # TODO: negative queries don't work, because they must be applied to the whole content, not just a
        # particular page or provision
        return [
            # content
            SimpleQueryString(
                query=query,
                fields=["content"],
                **self.advanced_simple_query_string_options,
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
                    **self.advanced_simple_query_string_options,
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
                            **self.advanced_simple_query_string_options,
                        ),
                        SimpleQueryString(
                            query=self.query,
                            fields=["provisions.title^4", "provisions.parent_titles^2"],
                            **self.advanced_simple_query_string_options,
                        ),
                    ],
                ),
            ),
        ]

    def build_aggs(self):
        aggs = {}
        for field in self.facet_fields:
            facet = field.get("facet", TermsFacet)
            aggs[field["field"]] = facet(field=field["field"], **field["options"])
        return aggs

    def build_knn_query(self, search, mode):
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
                            "query_vector": self.get_query_embedding(self.query),
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

    def get_query_embedding(self, query):
        return get_query_embedding(query)

    def get_field(self, field):
        options = (
            self.search_fields.get(field, {})
            or self.advanced_search_fields.get(field, {})
            or {}
        )
        if "boost" in options:
            return f'{field}^{options["boost"]}'
        return field


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
