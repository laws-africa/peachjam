import logging
from typing import Any, Iterable, List, Literal, Optional, Self

from django.conf import settings
from pydantic import BaseModel

from peachjam_search.compiler import ElasticsearchSearchCompiler, RetrieverSearch
from peachjam_search.search_pipeline import (
    FilterClause,
    QueryAnalyser,
    QueryAnalysis,
    SearchPlan,
    SearchPlanner,
    SearchQuery,
    serialise,
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
            self.analysis = self.analyser.analyse(self.search_query)
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
            "inputs": serialise(self.search_query),
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

    def to_filter_clauses(self) -> tuple[FilterClause, ...]:
        clauses = []
        for key, value in self.model_dump(exclude_none=True).items():
            field, *lookup = key.split("__")
            lookup = lookup[0] if lookup else "exact"

            if field.startswith("frbr_"):
                # ES fields are named with frbr_uri_...
                field = "frbr_uri_" + field[5:]

            if lookup == "exact":
                clauses.append(FilterClause(field=field, operator="term", value=value))
            elif lookup == "in":
                clauses.append(
                    FilterClause(field=field, operator="terms", value=tuple(value))
                )
            else:
                raise ValueError(f"Unsupported lookup: {lookup}")
        return tuple(clauses)


def make_portion_search_query(
    query: str,
    filters: Iterable[PortionSearchFilters] = (),
    mode: Literal["text", "semantic", "hybrid"] = "text",
) -> SearchQuery:
    """Build the regular query used by the portion-search pipeline."""

    hard_filters = tuple(
        filter_clause
        for portion_filters in filters
        for filter_clause in portion_filters.to_filter_clauses()
    )
    return SearchQuery(
        query=query,
        field_queries={},
        mode=mode,
        filters={},
        hard_filters=hard_filters,
        facets=[],
        page=1,
        page_size=SearchQuery.default_page_size,
        ordering="-score",
        explain=False,
        source=PortionSearchEngine.default_source,
        highlight={},
    )


class PortionSearchEngine(SearchEngine):
    """Search portions through the standard engine pipeline."""

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

    def __init__(
        self,
        search_query: SearchQuery,
        planner: SearchPlanner | None = None,
        compiler: ElasticsearchSearchCompiler | None = None,
        analyser: QueryAnalyser | None = None,
    ) -> None:
        super().__init__(
            search_query=search_query,
            analyser=analyser,
            planner=planner,
            compiler=compiler,
        )
