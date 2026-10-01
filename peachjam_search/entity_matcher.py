import re
import string
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlencode

from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _

from peachjam.models import Court, Judge, Locality


@dataclass(frozen=True)
class EntitySearchHit:
    entity_type: str
    type_label: str
    entity_id: int
    label: str
    url: str
    match_type: str
    confidence: float
    result_id: str | None = None


@dataclass(frozen=True)
class CandidateMatch:
    entity: Model
    match_type: str
    confidence: float


class EntityProvider:
    entity_type = ""
    type_label = ""
    model = None
    fields = ("id", "name")
    cache_timeout = 60 * 60

    def get_queryset(self) -> QuerySet:
        return self.model.objects.all()

    def get_entities(self) -> list[Model]:
        cache_key = f"peachjam-search-entity-provider:{self.entity_type}:v1"
        return cache.get_or_set(
            cache_key,
            lambda: list(self.get_queryset().only(*self.fields)),
            self.cache_timeout,
        )

    def get_label(self, entity) -> str:
        return entity.name

    def get_url(self, entity) -> str:
        return entity.get_absolute_url()

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        raise NotImplementedError()

    def suggestion_values(self, entity) -> list[str]:
        """Return normalized values which may trigger a typeahead suggestion."""
        return [normalize(self.get_label(entity))]

    def suggest(self, normalized_query: str) -> list[CandidateMatch]:
        matches = []
        for entity in self.get_entities():
            values = self.suggestion_values(entity)
            if normalized_query in values:
                matches.append(CandidateMatch(entity, "exact", 1.0))
            elif any(value.startswith(normalized_query) for value in values):
                matches.append(CandidateMatch(entity, "prefix", 0.8))
        return matches

    def build_hit(self, match: CandidateMatch) -> EntitySearchHit:
        entity = match.entity
        return EntitySearchHit(
            entity_type=self.entity_type,
            type_label=self.type_label,
            entity_id=entity.pk,
            label=self.get_label(entity),
            url=self.get_url(entity),
            match_type=match.match_type,
            confidence=match.confidence,
        )


class CourtEntityProvider(EntityProvider):
    entity_type = "court"
    type_label = _("Court")
    model = Court
    fields = ("id", "name", "code")

    def suggestion_values(self, court) -> list[str]:
        return [normalize(court.name), normalize(court.code)]

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        matches = []

        for court in self.get_entities():
            normalized_name = normalize(court.name)
            normalized_code = normalize(court.code)

            if query == court.name:
                matches.append(CandidateMatch(court, "exact", 1.0))
            elif normalized_query == normalized_name:
                matches.append(CandidateMatch(court, "normalized exact", 0.98))
            elif normalized_query == normalized_code:
                matches.append(CandidateMatch(court, "code exact", 0.98))

        return matches


class JudgeEntityProvider(EntityProvider):
    entity_type = "judge"
    type_label = _("Judge")
    model = Judge

    def suggestion_values(self, judge) -> list[str]:
        normalized_name = normalize(judge.name)
        return [normalized_name, *normalized_name.split()]

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        matches = []
        token_matches = []
        query_tokens = tokenize(normalized_query)

        for judge in self.get_entities():
            normalized_name = normalize(judge.name)
            name_tokens = tokenize(normalized_name)

            if query == judge.name:
                matches.append(CandidateMatch(judge, "exact", 1.0))
            elif normalized_query == normalized_name:
                matches.append(CandidateMatch(judge, "normalized exact", 0.98))
            elif self.is_token_match(query_tokens, name_tokens):
                token_matches.append(judge)

        if len(token_matches) == 1:
            matches.append(CandidateMatch(token_matches[0], "unique token", 0.9))

        return matches

    def is_token_match(self, query_tokens: list[str], name_tokens: list[str]) -> bool:
        """Match judge names conservatively by token.

        A single-token query must be at least four characters and match one
        name token. Multi-token queries must all be present in the judge name.
        The caller only promotes token matches when exactly one judge matches,
        so common or ambiguous names are not surfaced as entity hits.
        """
        if not query_tokens:
            return False

        if len(query_tokens) == 1:
            return len(query_tokens[0]) >= 4 and query_tokens[0] in name_tokens

        return set(query_tokens).issubset(set(name_tokens))


class LocalityEntityProvider(EntityProvider):
    entity_type = "locality"
    type_label = _("Locality")
    model = Locality
    fields = ("id", "name", "code", "jurisdiction")

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().select_related("jurisdiction")

    def get_url(self, entity) -> str:
        try:
            return reverse(
                "locality_legislation_list",
                kwargs={"code": entity.place_code()},
            )
        except NoReverseMatch:
            # Some site URL configs don't have a locality legislation route.
            return f"{reverse('legislation_list')}?{urlencode({'localities': entity.name})}"

    def suggestion_values(self, locality) -> list[str]:
        return [
            normalize(locality.name),
            normalize(re.sub(r"\s*\([^)]*\)", "", locality.name)),
            normalize(locality.place_code()),
        ]

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        matches = []

        for locality in self.get_entities():
            normalized_names = [
                normalize(locality.name),
                normalize(re.sub(r"\s*\([^)]*\)", "", locality.name)),
            ]
            normalized_place_code = normalize(locality.place_code())

            if query == locality.name:
                matches.append(CandidateMatch(locality, "exact", 1.0))
            elif normalized_query in normalized_names:
                matches.append(CandidateMatch(locality, "normalized exact", 0.98))
            elif normalized_query == normalized_place_code:
                matches.append(CandidateMatch(locality, "place code exact", 0.98))

        return matches


class EntityMatcher:
    default_providers = [
        CourtEntityProvider,
        JudgeEntityProvider,
        LocalityEntityProvider,
    ]
    max_query_length = 50
    max_suggestion_query_length = 100
    _instance = None

    def __init__(self, providers: Iterable[EntityProvider] | None = None):
        self.providers = (
            list(providers)
            if providers is not None
            else [provider() for provider in self.default_providers]
        )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def match(self, query: str) -> list[EntitySearchHit]:
        query = (query or "").strip()
        if len(query) > self.max_query_length:
            return []

        normalized_query = normalize(query)
        if not normalized_query:
            return []

        matches = []
        for provider in self.providers:
            matches.extend(
                provider.build_hit(match)
                for match in provider.match(query, normalized_query)
            )

        return sorted(matches, key=lambda hit: hit.confidence, reverse=True)

    def suggest(self, query: str, limit_per_type: int = 3) -> list[EntitySearchHit]:
        """Return prefix matches without weakening full-search entity matching."""
        query = (query or "").strip()
        if len(query) > self.max_suggestion_query_length:
            return []

        normalized_query = normalize(query)
        if not normalized_query:
            return []

        hits = []
        for provider in self.providers:
            provider_hits = [
                provider.build_hit(match)
                for match in provider.suggest(normalized_query)
            ]
            provider_hits.sort(
                key=lambda hit: (-hit.confidence, hit.label.casefold(), hit.entity_id)
            )
            hits.extend(provider_hits[:limit_per_type])
        return hits

    def match_selected(
        self,
        query: str,
        entity_type: str,
        entity_id: str | None = None,
        limit: int = 3,
    ) -> list[EntitySearchHit]:
        """Resolve an explicitly selected suggestion to its existing entity card."""
        normalized_query = normalize((query or "").strip())
        if not normalized_query:
            return []

        for provider in self.providers:
            if provider.entity_type != entity_type:
                continue
            matches = [
                CandidateMatch(entity, "selected suggestion", 1.0)
                for entity in provider.get_entities()
                if normalize(provider.get_label(entity)) == normalized_query
                and (entity_id is None or str(entity.pk) == str(entity_id))
            ]
            matches.sort(key=lambda match: match.entity.pk)
            return [provider.build_hit(match) for match in matches[:limit]]
        return []


def normalize(value: str) -> str:
    # Canonicalize names and queries so exact matching is case- and punctuation-insensitive.
    value = value.casefold()
    value = value.translate(str.maketrans("", "", string.punctuation))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(value: str) -> list[str]:
    return [token for token in value.split() if len(token) >= 3]
