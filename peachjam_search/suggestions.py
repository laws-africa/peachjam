"""Combined find-as-you-type suggestions for public search."""

import logging
from dataclasses import dataclass

from django.db.models import Case, IntegerField, Value, When
from django.utils.translation import gettext_lazy as _
from elastic_transport import ConnectionError as ElasticsearchConnectionError
from elastic_transport import ConnectionTimeout

from peachjam.models import Flynote, Judgment
from peachjam_search.compiler import ElasticsearchSearchCompiler
from peachjam_search.entity_matcher import EntityMatcher, normalize
from peachjam_search.flynotes import FlynoteSearchMatcher

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchSuggestion:
    value: str
    type: str
    type_label: str
    target_id: str | None = None
    match_rank: int = 1
    source_rank: int = 0

    def as_dict(self):
        return {
            "value": self.value,
            "type": self.type,
            "type_label": self.type_label,
            "target_id": self.target_id,
        }


class DocumentSuggestionProvider:
    suggestion_type = "document"
    limit = 5

    def suggest(self, query: str) -> list[SearchSuggestion]:
        try:
            response = ElasticsearchSearchCompiler().suggest(query, size=self.limit)
        except (ElasticsearchConnectionError, ConnectionTimeout):
            # Suggestions are an enhancement. If Elasticsearch is temporarily
            # unavailable, keep serving suggestions from PostgreSQL instead of
            # failing the complete typeahead request.
            log.warning("Unable to load document search suggestions", exc_info=True)
            return []
        options = response.suggest.prefix[0].options
        suggestions = []
        for source_rank, option in enumerate(options):
            option_data = option.to_dict()
            source = option_data.get("_source", {})
            type_label = source.get("nature") or _("Document")
            value = str(option.text)
            suggestions.append(
                SearchSuggestion(
                    value=value,
                    type=self.suggestion_type,
                    type_label=str(type_label),
                    target_id=source.get("expression_frbr_uri") or None,
                    match_rank=0 if normalize(value) == normalize(query) else 1,
                    source_rank=source_rank,
                )
            )
        return suggestions


class FlynoteSuggestionProvider:
    suggestion_type = "flynote"
    limit = 5

    def suggest(self, query: str) -> list[SearchSuggestion]:
        if not Judgment.flynote_tree_enabled():
            return []
        normalized_query = query.upper()
        flynotes = (
            FlynoteSearchMatcher.with_document_counts(
                Flynote.objects.prefix_matching_names(query)
            )
            .annotate(
                exact_match=Case(
                    When(search_name=normalized_query, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
            )
            .filter(doc_count__gt=0)
            .order_by("exact_match", "-doc_count", "name")[: self.limit]
        )
        return [
            SearchSuggestion(
                value=flynote.name,
                type=self.suggestion_type,
                type_label=str(_("Legal topic")),
                target_id=str(flynote.pk),
                match_rank=flynote.exact_match,
                source_rank=source_rank,
            )
            for source_rank, flynote in enumerate(flynotes)
        ]


class EntitySuggestionProvider:
    limit_per_type = 3

    def suggest(self, query: str) -> list[SearchSuggestion]:
        positions = {}
        suggestions = []
        for hit in EntityMatcher.get_instance().suggest(
            query, limit_per_type=self.limit_per_type
        ):
            source_rank = positions.get(hit.entity_type, 0)
            suggestions.append(
                SearchSuggestion(
                    value=hit.label,
                    type=hit.entity_type,
                    type_label=str(hit.type_label),
                    target_id=str(hit.entity_id),
                    match_rank=0 if hit.match_type == "exact" else 1,
                    source_rank=source_rank,
                )
            )
            positions[hit.entity_type] = source_rank + 1
        return suggestions


class SearchSuggestionService:
    """Gather, rank and limit suggestions from all searchable content sources."""

    min_query_length = 3
    max_query_length = 100
    max_results = 10
    max_results_per_type = 3
    type_priority = {
        "document": 0,
        "flynote": 1,
        "court": 2,
        "judge": 3,
        "locality": 4,
    }
    providers = (
        DocumentSuggestionProvider,
        FlynoteSuggestionProvider,
        EntitySuggestionProvider,
    )

    def suggest(self, query: str) -> list[dict]:
        query = (query or "").replace("\x00", " ").strip()
        if not self.min_query_length <= len(query) <= self.max_query_length:
            return []

        candidates = []
        for provider_class in self.providers:
            candidates.extend(provider_class().suggest(query))

        candidates.sort(
            key=lambda suggestion: (
                suggestion.match_rank,
                suggestion.source_rank,
                self.type_priority.get(suggestion.type, len(self.type_priority)),
                suggestion.value.casefold(),
            )
        )
        selected = self.select_balanced(candidates)
        return [suggestion.as_dict() for suggestion in selected]

    def select_balanced(
        self, candidates: list[SearchSuggestion]
    ) -> list[SearchSuggestion]:
        selected = []
        deferred = []
        counts = {}
        seen = set()

        for suggestion in candidates:
            key = (suggestion.type, normalize(suggestion.value))
            if key in seen:
                continue
            seen.add(key)
            count = counts.get(suggestion.type, 0)
            if count < self.max_results_per_type:
                selected.append(suggestion)
                counts[suggestion.type] = count + 1
            else:
                deferred.append(suggestion)

        remaining = max(0, self.max_results - len(selected))
        selected.extend(deferred[:remaining])
        return selected[: self.max_results]
