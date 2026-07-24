"""Analysis and planning types for document search.

Analysis looks at the query and determines how it should be treated.

Planning looks at the query and analysis and decides which retrieval and ranking behaviours to use. It describes
search behaviour without attempting to recreate Elasticsearch's entire query DSL.  The Elasticsearch compiler
keeps ownership of filters, aggregations, retrievers and concrete query objects.
"""

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Literal

from peachjam.models import pj_settings
from peachjam_search.classifier import QueryClassifier
from peachjam_search.profiles import (
    SearchProfile,
    SearchProfileSet,
    get_default_search_profile_set,
)


@dataclass(frozen=True)
class SearchQuery:
    """Details of a user's search query for a single document search."""

    query: str | None
    field_queries: dict[str, str]
    mode: Literal["text", "semantic", "hybrid"]
    filters: dict[str, Any]
    facets: list[str]
    page: int
    page_size: int
    ordering: Literal["-score", "date", "-date"]
    explain: bool
    source: dict[str, Any] | list[str] | None = None
    highlight: dict[str, Any] | None = None

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


@dataclass(frozen=True)
class RankFeature:
    """A rank-feature signal with values already selected by the planner."""

    field: str
    boost: float | None
    saturation_pivot: float | None = None
    name: str = "pagerank"


@dataclass(frozen=True)
class PageRankSettings:
    """Site-specific PageRank calibration supplied to the planner."""

    boost_value: float | None
    pivot_value: float | None


@dataclass(frozen=True)
class SearchPlan:
    """The retrieval and ranking behaviour selected for one search request."""

    analysis: QueryAnalysis
    search_query: SearchQuery
    profile: SearchProfile
    mode: str
    retrieval_clauses: tuple[RetrievalClause, ...]
    ranking_signals: tuple[RankFeature, ...] = ()

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

    def __init__(
        self,
        profile_set: SearchProfileSet | None = None,
        pagerank_settings: PageRankSettings | None = None,
    ) -> None:
        self.profile_set = profile_set or get_default_search_profile_set()
        # Benchmarking can supply a site's known calibration without changing
        # the query compiler or reading the benchmark site's database.
        self.pagerank_settings = pagerank_settings

    def build(self, search_query: SearchQuery, analysis: QueryAnalysis) -> SearchPlan:
        if search_query.is_advanced:
            # don't use label classification search profiles for advanced searches
            profile = self.profile_set.default
        else:
            profile = self.profile_set.get_profile(analysis.intent)

        if search_query.is_advanced:
            # these handle advanced search, and can't be combined with normal search because they both
            # build queries to return nested content, and ES complains if multiple queries try to return the
            # same nested content fields
            retrieval_clauses = (
                RetrievalClause("advanced_per_field"),
                RetrievalClause("advanced_all"),
                RetrievalClause("advanced_content"),
            )
        elif search_query.mode in {"text", "hybrid"}:
            # these handle basic search
            retrieval_clauses = (
                RetrievalClause("basic"),
                RetrievalClause("content_phrase"),
                RetrievalClause("nested_pages"),
                RetrievalClause("nested_provisions"),
            )
        else:
            retrieval_clauses = ()

        ranking_signals = (
            (self.build_pagerank_signal(profile),)
            if search_query.mode in {"text", "hybrid"}
            else ()
        )
        return SearchPlan(
            analysis=analysis,
            search_query=search_query,
            profile=profile,
            mode="text" if search_query.is_advanced else search_query.mode,
            retrieval_clauses=retrieval_clauses,
            ranking_signals=ranking_signals,
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
