import re
import string
from dataclasses import dataclass
from typing import Iterable

from django.db.models import Model, QuerySet
from django.utils.translation import gettext_lazy as _

from peachjam.models import Court, Judge


@dataclass(frozen=True)
class EntitySearchHit:
    entity_type: str
    entity_id: int
    label: str
    url: str
    match_type: str
    confidence: float

    @property
    def type_label(self):
        return ENTITY_TYPE_LABELS.get(self.entity_type, self.entity_type)


@dataclass(frozen=True)
class CandidateMatch:
    entity: Model
    match_type: str
    confidence: float


class EntityProvider:
    entity_type = ""
    model = None

    def get_queryset(self) -> QuerySet:
        return self.model.objects.all()

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
            entity_id=entity.pk,
            label=self.get_label(entity),
            url=self.get_url(entity),
            match_type=match.match_type,
            confidence=match.confidence,
        )


class CourtEntityProvider(EntityProvider):
    entity_type = "court"
    model = Court

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        matches = []

        for court in self.get_queryset().only("id", "name", "code"):
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
    model = Judge

    def match(self, query: str, normalized_query: str) -> list[CandidateMatch]:
        matches = []
        token_matches = []
        query_tokens = tokenize(normalized_query)

        for judge in self.get_queryset().only("id", "name"):
            normalized_name = normalize(judge.name)
            name_tokens = tokenize(normalized_name)

            if query == judge.name:
                matches.append(CandidateMatch(judge, "exact", 1.0))
            elif normalized_query == normalized_name:
                matches.append(CandidateMatch(judge, "normalized exact", 0.98))
            elif is_judge_token_match(query_tokens, name_tokens):
                token_matches.append(judge)

        if len(token_matches) == 1:
            matches.append(CandidateMatch(token_matches[0], "unique token", 0.9))

        return matches


class EntityMatcher:
    default_providers = [CourtEntityProvider, JudgeEntityProvider]

    def __init__(self, providers: Iterable[EntityProvider] | None = None):
        self.providers = (
            list(providers)
            if providers is not None
            else [provider() for provider in self.default_providers]
        )

    def match(self, query: str) -> list[EntitySearchHit]:
        query = (query or "").strip()
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
    value = value.casefold()
    value = value.translate(str.maketrans("", "", string.punctuation))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def tokenize(value: str) -> list[str]:
    return [token for token in value.split() if len(token) >= 3]


def is_judge_token_match(query_tokens: list[str], name_tokens: list[str]) -> bool:
    if not query_tokens:
        return False

    if len(query_tokens) == 1:
        return len(query_tokens[0]) >= 4 and query_tokens[0] in name_tokens

    return set(query_tokens).issubset(set(name_tokens))


ENTITY_TYPE_LABELS = {
    "court": _("Court"),
    "judge": _("Judge"),
}
