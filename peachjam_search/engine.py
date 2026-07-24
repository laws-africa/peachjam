import logging
from typing import Any, List, Optional, Self

from django.conf import settings
from elasticsearch_dsl.query import Bool
from pydantic import BaseModel

from peachjam_search.compiler import ElasticsearchSearchCompiler, RetrieverSearch
from peachjam_search.search_pipeline import (
    QueryAnalyser,
    QueryAnalysis,
    SearchPlan,
    SearchPlanner,
    SearchQuery,
)

log = logging.getLogger(__name__)


class SearchEngine:
    """One-shot document-search orchestration.

    Inputs, analysis and plan are deliberately explicit instance data.  The
    compiler owns Elasticsearch details and receives a complete plan.
    """

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
            page_size=SearchQuery.default_page_size,
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

    def suggest(self, query: str) -> Any:
        return self.compiler.suggest(query)

    def build_debug_payload(self) -> dict[str, Any]:
        search = self.build_search()
        query = search.to_dict()
        return {
            "index": self.compiler.index,
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
        self.semantic_k = SearchPlanner.default_semantic_k

    def build_search(self) -> "RetrieverSearch":
        """Build the legacy portion search using a transient document plan.

        Portion search has its own input shape and filters, but shares the
        document retrieval and semantic-query compilation helpers. Supplying a
        concrete query and plan here keeps those helpers free of compatibility
        accessors.
        """
        self.search_query = SearchQuery(
            query=self.query,
            field_queries={},
            mode=self.mode,
            filters={},
            facets=[],
            page=1,
            page_size=SearchQuery.default_page_size,
            ordering="-score",
            explain=False,
            source=self.default_source,
            highlight={},
        )
        self.plan = SearchPlanner(semantic_k=self.semantic_k).build(
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
        inputs = {
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
        }
        if self.plan.semantic_retrieval:
            inputs.update(
                {
                    "semantic_k": self.plan.semantic_retrieval.k,
                    "semantic_num_candidates": self.plan.semantic_retrieval.num_candidates,
                }
            )
        return inputs

    def add_filters(self, search: "RetrieverSearch") -> "RetrieverSearch":
        search = search.filter("term", is_most_recent=True)

        for f in self.filters:
            search = search.query(Bool(filter=f.to_es_query()))

        return search
