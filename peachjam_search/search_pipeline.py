"""Analysis and planning types for document search.

Analysis looks at the query and determines how it should be treated.

Planning looks at the query and analysis and decides which retrieval and ranking behaviours to use. It describes
search behaviour without attempting to recreate Elasticsearch's entire query DSL.  The Elasticsearch compiler
keeps ownership of filters, aggregations, retrievers and concrete query objects.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, ClassVar, Literal

from django.conf import settings

from peachjam.models import pj_settings
from peachjam_search.classifier import QueryClassifier
from peachjam_search.profiles import (
    SearchProfile,
    SearchProfileSet,
    get_default_search_profile_set,
)


@dataclass(frozen=True)
class FilterClause:
    """An exact Elasticsearch filter that must apply to every retriever."""

    field: str
    operator: Literal["term", "terms"]
    value: Any


@dataclass(frozen=True)
class SearchQuery:
    """Details of a user's search query for a single document search."""

    default_page_size: ClassVar[int] = 10
    default_facets: ClassVar[list[str]] = [
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
    default_source: ClassVar[dict[str, list[str]]] = {
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
    default_highlight: ClassVar[dict[str, dict[str, Any]]] = {
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

    query: str | None
    field_queries: dict[str, str]
    mode: Literal["text", "semantic", "hybrid"]
    filters: dict[str, Any]
    facets: list[str]
    page: int
    page_size: int
    ordering: Literal["-score", "date", "-date"]
    explain: bool
    hard_filters: tuple[FilterClause, ...] = ()
    source: dict[str, Any] | list[str] = field(
        default_factory=lambda: deepcopy(SearchQuery.default_source)
    )
    highlight: dict[str, Any] = field(
        default_factory=lambda: deepcopy(SearchQuery.default_highlight)
    )

    @property
    def is_advanced(self):
        return bool(self.field_queries)


@dataclass(frozen=True)
class QueryAnalysis:
    """The interpreted query available to a search planner."""

    raw_query: str
    clean_query: str | None = None
    intent: str | None = None
    confidence: float | None = None
    components: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class RetrievalClause:
    """A named retrieval behaviour understood by the ES compiler."""

    name: str
    query: str | None = None
    boost: float = 1.0


@dataclass(frozen=True)
class RankFeature:
    """A rank-feature signal with values already selected by the planner."""

    field: str
    boost: float | None
    saturation_pivot: float | None = None
    semantic_factor: float = 0.1
    name: str = "pagerank"


@dataclass(frozen=True)
class PageRankSettings:
    """Site-specific PageRank calibration supplied to the planner."""

    boost_value: float | None
    pivot_value: float | None


@dataclass(frozen=True)
class KnnRetrieval:
    """Resolved semantic retrieval parameters for one search plan."""

    embedding_field: str
    k: int
    num_candidates: int
    similarity: float


@dataclass(frozen=True)
class RrfRetrieval:
    """Resolved reciprocal-rank fusion parameters for one search plan."""

    rank_window_size: int
    rank_constant: int


@dataclass(frozen=True)
class SearchPlan:
    """The retrieval and ranking behaviour selected for one search request."""

    analysis: QueryAnalysis
    search_query: SearchQuery
    profile: SearchProfile
    mode: str
    retrieval_clauses: tuple[RetrievalClause, ...]
    ranking_signals: tuple[RankFeature, ...] = ()
    semantic_retrieval: KnnRetrieval | None = None
    rrf_retrieval: RrfRetrieval | None = None

    def to_dict(self):
        return serialise(self)


class QueryAnalyser:
    """Adapt the query classifier to the search-planning interface."""

    def __init__(self, classifier=None):
        self.classifier = classifier or QueryClassifier()

    def analyse(self, query):
        qclass = self.classifier.classify(query or "")
        return QueryAnalysis(
            raw_query=query or "",
            clean_query=qclass.query_clean,
            intent=qclass.label.value if qclass.label else None,
            confidence=qclass.confidence,
        )


class SearchPlanner:
    """Based on a query and its analysis, builds a search plan that describes the retrieval and ranking behaviour."""

    default_semantic_k = 5 * SearchQuery.default_page_size * 3
    default_semantic_num_candidates_factor = 10
    default_semantic_embedding_field = "content_chunks.text_embedding"
    default_semantic_similarity = 0.4
    default_rrf_rank_window_size = default_semantic_k
    default_rrf_rank_constant = 60

    def __init__(
        self,
        profile_set: SearchProfileSet | None = None,
        pagerank_settings: PageRankSettings | None = None,
        semantic_k: int | None = None,
    ) -> None:
        self.profile_set = profile_set or get_default_search_profile_set()
        # Benchmarking can supply a site's known calibration without changing
        # the query compiler or reading the benchmark site's database.
        self.pagerank_settings = pagerank_settings
        self.semantic_k = semantic_k or self.default_semantic_k

    def build(self, search_query: SearchQuery, analysis: QueryAnalysis) -> SearchPlan:
        if search_query.is_advanced:
            # don't use label classification search profiles for advanced searches
            profile = self.profile_set.default
        else:
            profile = self.profile_set.get_profile(analysis.intent)

        if search_query.is_advanced:
            retrieval_clauses = [RetrievalClause("advanced_per_field")]
            if search_query.field_queries.get("all"):
                retrieval_clauses.append(RetrievalClause("advanced_all"))
            elif search_query.field_queries.get("content"):
                retrieval_clauses.append(RetrievalClause("advanced_content"))
            retrieval_clauses = tuple(retrieval_clauses)
        elif search_query.mode in {"text", "hybrid"}:
            retrieval_clauses = []
            if search_query.query:
                retrieval_clauses = [
                    RetrievalClause(
                        "basic",
                        query=search_query.query,
                        boost=profile.basic_query_boost,
                    )
                ]
                if " " in search_query.query:
                    retrieval_clauses.append(
                        RetrievalClause(
                            "basic_phrase",
                            query=search_query.query,
                            boost=profile.basic_phrase_query_boost,
                        )
                    )
                retrieval_clauses.extend(
                    [
                        RetrievalClause(
                            "content_phrase",
                            query=search_query.query,
                            boost=profile.content_phrase_query_boost,
                        ),
                        RetrievalClause(
                            "nested_pages",
                            query=search_query.query,
                            boost=profile.nested_pages_query_boost,
                        ),
                        RetrievalClause(
                            "nested_provisions",
                            query=search_query.query,
                            boost=profile.nested_provisions_query_boost,
                        ),
                    ]
                )
            retrieval_clauses = tuple(retrieval_clauses)
        else:
            retrieval_clauses = ()

        plan_mode = "text" if search_query.is_advanced else search_query.mode
        ranking_signals = (
            (self.build_pagerank_signal(profile),)
            if search_query.mode in {"text", "hybrid"}
            else ()
        )
        semantic_retrieval = (
            self.build_semantic_retrieval()
            if plan_mode in {"semantic", "hybrid"}
            else None
        )
        rrf_retrieval = (
            self.build_rrf_retrieval(search_query) if plan_mode == "hybrid" else None
        )
        return SearchPlan(
            analysis=analysis,
            search_query=search_query,
            profile=profile,
            mode=plan_mode,
            retrieval_clauses=retrieval_clauses,
            ranking_signals=ranking_signals,
            semantic_retrieval=semantic_retrieval,
            rrf_retrieval=rrf_retrieval,
        )

    def build_semantic_retrieval(self) -> KnnRetrieval:
        return KnnRetrieval(
            embedding_field=self.default_semantic_embedding_field,
            k=self.semantic_k,
            num_candidates=self.semantic_k
            * self.default_semantic_num_candidates_factor,
            similarity=self.default_semantic_similarity,
        )

    def build_rrf_retrieval(self, search_query: SearchQuery) -> RrfRetrieval:
        return RrfRetrieval(
            rank_window_size=max(
                self.default_rrf_rank_window_size,
                search_query.page * search_query.page_size,
            ),
            rank_constant=self.default_rrf_rank_constant,
        )

    def build_pagerank_signal(self, profile: SearchProfile) -> RankFeature:
        """Resolve profile and site calibration into a compiler-ready signal."""
        supplied_settings = self.pagerank_settings
        if profile.use_pagerank_settings:
            settings = supplied_settings or self.get_pagerank_settings()
            boost = settings.boost_value
            pivot = settings.pivot_value
        else:
            boost = profile.pagerank_boost_value
            # A supplied site calibration deliberately owns the pivot even
            # when a tuned profile owns the boost. The pivot is index-specific.
            pivot = (
                supplied_settings.pivot_value
                if supplied_settings is not None
                else profile.pagerank_pivot_value
            )

        return RankFeature(
            field="ranking",
            boost=boost,
            saturation_pivot=pivot,
        )

    @staticmethod
    def get_pagerank_settings() -> PageRankSettings:
        """Read the current site's PageRank calibration for production plans."""
        settings = pj_settings()
        return PageRankSettings(
            boost_value=settings.pagerank_boost_value,
            pivot_value=settings.pagerank_pivot_value,
        )


def serialise(value):
    """Return a JSON-friendly representation of pipeline dataclasses."""
    if is_dataclass(value):
        return {key: serialise(child) for key, child in asdict(value).items()}
    if isinstance(value, dict):
        return {key: serialise(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialise(child) for child in value]
    return value
