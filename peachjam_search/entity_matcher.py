import re
import string
from dataclasses import dataclass
from typing import Iterable

from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.utils.translation import gettext_lazy as _

from peachjam.models import Court, Judge


@dataclass(frozen=True)
class EntitySearchHit:
    entity_type: str
    type_label: str
    entity_id: int
    label: str
    url: str
    match_type: str
    confidence: float


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


class EntityMatcher:
    default_providers = [CourtEntityProvider, JudgeEntityProvider]
    max_query_length = 50
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


def normalize(value: str) -> str:
    # Canonicalize names and queries so exact matching is case- and punctuation-insensitive.
    value = value.casefold()
    value = value.translate(str.maketrans("", "", string.punctuation))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(value: str) -> list[str]:
    return [token for token in value.split() if len(token) >= 3]
