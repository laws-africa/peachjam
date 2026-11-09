"""Deterministic case-history suggestion analysis.

Methodology
===========

The analyser starts with a changed judgment and retrieves a deliberately small set
of possible earlier stages using exact, explainable identifiers: neutral citations,
resolved citation links, case numbers, and an exact signature of distinctive party
names. It then looks for procedural language near each reference (for example,
"appeal against the judgment"), validates that the target predates the source and
that the court direction is plausible, and scores the combined evidence. Party-name
matching is supporting evidence, never sufficient on its own without procedural and
court context.

The result is a suggestion with the source evidence and individual signals retained
for an editor. Strong suggestions and suggestions needing review are stored; weak
candidates are withheld. Accepted or rejected editorial decisions survive reruns,
while obsolete pending suggestions are marked superseded. Analysis also runs in the
reverse direction so that adding an older judgment can unlock a relationship from an
already-present later judgment.

This module intentionally favours precision and auditability over recall. It does not
use an LLM, fuzzy semantic similarity, or automatically create authoritative case
histories.
"""

import collections
import hashlib
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from django.db.models import Q

from peachjam.models import (
    CaseHistory,
    CaseHistorySuggestion,
    CaseNumber,
    CitationLink,
    Judgment,
)

PIPELINE_VERSION = "deterministic-v2"
SCAN_CHARS = 50_000

NEUTRAL_CITATION_RE = re.compile(
    r"\[(?:18|19|20)\d{2}\]\s+[A-Z][A-Z0-9-]{2,24}\s+\d+[A-Z]?",
    re.I,
)
CASE_NUMBER_RE = re.compile(
    r"(?:case\s+(?:no\.?|number)|under\s+case\s+number)\s*[:#-]?\s*"
    r"([A-Z]{0,12}\s*\d{1,8}(?:/|-|\s+of\s+)\d{2,4})",
    re.I,
)

RELATION_PATTERNS = collections.OrderedDict(
    [
        (
            CaseHistorySuggestion.RelationshipType.CONFIRMATION_OF,
            re.compile(
                r"(?:application|proceedings?)\s+for\s+confirmation\s+of|"
                r"confirmation\s+of\s+(?:an?\s+|the\s+)?order",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.RESCISSION_OF,
            re.compile(
                r"(?:application\s+for\s+)?rescission\s+of\s+(?:an?\s+|the\s+)?"
                r"(?:judgment|order)|rescind(?:ed|ing)?\s+(?:an?\s+|the\s+)?"
                r"(?:judgment|order)",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.REMITTAL_FOLLOWING,
            re.compile(
                r"following\s+(?:an?\s+|the\s+)?remittal|"
                r"after\s+(?:the\s+)?matter\s+(?:had\s+)?been\s+remitted|"
                r"remitted\s+back\s+by",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.REVIEW_OF,
            re.compile(
                r"application\s+(?:for|to)\s+(?:the\s+)?review\s+of|"
                r"review\s+of\s+(?:an?\s+|the\s+)?(?:judgment|decision|order)",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.LEAVE_TO_APPEAL_FROM,
            re.compile(
                r"application(?:s)?\s+for\s+leave\s+to\s+appeal\s+"
                r"(?:from|against)|leave\s+to\s+appeal\s+(?:from|against)",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.APPEAL_FROM,
            re.compile(
                r"on\s+(?:an?\s+|applications?\s+for\s+leave\s+to\s+)?"
                r"appeal\s+from|appeal(?:s|ed|ing)?\s+against\s+(?:an?\s+|the\s+)?"
                r"(?:judgment|decision|order)|appeal\s+lies?\s+against",
                re.I,
            ),
        ),
        (
            CaseHistorySuggestion.RelationshipType.RELATED_PROCEEDING,
            re.compile(
                r"(?:this\s+(?:matter|application)\s+is\s+)?(?:a\s+)?sequel\s+to|"
                r"previously\s+before\s+(?:this|the)\s+court|"
                r"earlier\s+proceedings\s+(?:between|involving)",
                re.I,
            ),
        ),
    ]
)

JUDGMENT_LABEL_RE = re.compile(
    r"(?:SCA|High\s+Court|Full\s+Court|Labour\s+Appeal\s+Court|"
    r"court\s+below|court\s+a\s+quo|earlier|previous|impugned)\s+judgment|"
    r"judgment\s+(?:under|on)\s+appeal",
    re.I,
)
AUTHORITY_MARKER_RE = re.compile(
    r"\b(?:see\s+also|see|cf|compare|relying\s+on|citing|followed|distinguished)\b",
    re.I,
)

STOPWORDS = {
    "accident",
    "africa",
    "african",
    "agency",
    "and",
    "another",
    "applicant",
    "appellants",
    "board",
    "cape",
    "commission",
    "commissioner",
    "council",
    "department",
    "development",
    "director",
    "education",
    "fund",
    "gauteng",
    "general",
    "government",
    "health",
    "justice",
    "limited",
    "ltd",
    "minister",
    "municipality",
    "national",
    "others",
    "police",
    "president",
    "property",
    "province",
    "provincial",
    "pty",
    "public",
    "registrar",
    "republic",
    "respondent",
    "respondents",
    "service",
    "services",
    "south",
    "state",
    "the",
    "zacc",
    "zasca",
}


@dataclass
class CandidateMatch:
    historical_judgment: Judgment
    methods: set[str] = field(default_factory=set)
    positions: list[int] = field(default_factory=list)


def compact(value):
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_case_number(value):
    value = compact(value).upper().replace(" OF ", "/")
    return re.sub(r"[^A-Z0-9]", "", value)


def party_tokens(value):
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", (value or "").lower())
    return frozenset(
        token
        for token in re.findall(r"[a-z][a-z'-]+", value)
        if len(token) > 2 and token not in STOPWORDS
    )


def party_overlap(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def relationship_in(value):
    earliest = None
    for relationship_type, pattern in RELATION_PATTERNS.items():
        match = pattern.search(value)
        if match and (earliest is None or match.start() < earliest[1].start()):
            earliest = (relationship_type, match)
    return earliest or (None, None)


def nearest_relationship(value, reference_position):
    nearest = None
    for relationship_type, pattern in RELATION_PATTERNS.items():
        for match in pattern.finditer(value):
            distance = min(
                abs(reference_position - match.start()),
                abs(reference_position - match.end()),
            )
            if nearest is None or distance < nearest[2]:
                nearest = (relationship_type, match, distance)
    return nearest or (None, None, None)


class CaseHistorySuggestionService:
    """Generate deterministic case-history suggestions for one changed judgment."""

    def suggest(self, judgment):
        if not getattr(judgment, "document_content", None):
            return 0

        # First treat the changed judgment as the later procedural stage. Then
        # treat it as a newly available historical stage and recheck only likely
        # later sources, rather than rescanning the full corpus.
        count = self.generate_for_source(judgment, supersede=True)
        for later in self.find_later_sources(judgment):
            count += self.generate_for_source(
                later, target_ids={judgment.pk}, supersede=False
            )
        return count

    def find_later_sources(self, judgment):
        # Resolved links and exact neutral-citation text are the strongest reverse
        # lookup keys. Exact party signatures cover unreported earlier stages.
        later_ids = set(
            CitationLink.objects.filter(url__contains=judgment.work_frbr_uri)
            .exclude(document_id=judgment.pk)
            .values_list("document_id", flat=True)
        )
        if judgment.mnc:
            later_ids.update(
                Judgment.objects.filter(
                    date__gt=judgment.date,
                    document_content__content_text__icontains=judgment.mnc,
                ).values_list("pk", flat=True)[:200]
            )

        signature = party_tokens(judgment.case_name or judgment.title)
        if len(signature) >= 2:
            anchor = max(signature, key=len)
            possible = (
                Judgment.objects.filter(
                    date__gt=judgment.date,
                    case_name__icontains=anchor,
                )
                .exclude(pk=judgment.pk)
                .only("pk", "case_name", "title")[:200]
            )
            later_ids.update(
                candidate.pk
                for candidate in possible
                if party_tokens(candidate.case_name or candidate.title) == signature
            )

        return Judgment.objects.filter(pk__in=later_ids).select_related(
            "court", "court__court_class", "document_content", "work"
        )

    def generate_for_source(self, judgment, target_ids=None, supersede=True):
        raw_text = judgment.document_content.content_text or ""
        text = compact(raw_text)[:SCAN_CHARS]
        if not text:
            return 0

        fingerprint = self.content_fingerprint(judgment, text)
        matches = self.find_matches(judgment, text)
        if target_ids is not None:
            matches = {pk: match for pk, match in matches.items() if pk in target_ids}

        found_keys = set()
        saved = 0
        for match in matches.values():
            values = self.evaluate(judgment, match, text, fingerprint)
            if (
                not values
                or values["disposition"] == CaseHistorySuggestion.Disposition.REJECT
            ):
                continue
            key = (
                match.historical_judgment.pk,
                values["relationship_type"],
            )
            found_keys.add(key)
            suggestion = CaseHistorySuggestion.objects.filter(
                judgment=judgment,
                historical_judgment=match.historical_judgment,
                relationship_type=values["relationship_type"],
                pipeline_version=PIPELINE_VERSION,
            ).first()
            if suggestion and suggestion.status in {
                CaseHistorySuggestion.Status.ACCEPTED,
                CaseHistorySuggestion.Status.REJECTED,
            }:
                # Editorial decisions are durable evaluation data. A pipeline
                # rerun must not silently reopen or overwrite them.
                continue
            if suggestion:
                for name, value in values.items():
                    setattr(suggestion, name, value)
                suggestion.status = CaseHistorySuggestion.Status.PROPOSED
                suggestion.save()
            else:
                CaseHistorySuggestion.objects.create(
                    judgment=judgment,
                    historical_judgment=match.historical_judgment,
                    pipeline_version=PIPELINE_VERSION,
                    **values,
                )
            saved += 1

        if supersede:
            # Superseding rather than deleting preserves an audit trail and lets
            # us explain why a previously visible suggestion disappeared.
            pending = CaseHistorySuggestion.objects.filter(
                judgment=judgment,
                pipeline_version=PIPELINE_VERSION,
                status=CaseHistorySuggestion.Status.PROPOSED,
            )
            for suggestion in pending:
                key = (suggestion.historical_judgment_id, suggestion.relationship_type)
                if key not in found_keys:
                    suggestion.status = CaseHistorySuggestion.Status.SUPERSEDED
                    suggestion.save(update_fields=["status", "updated_at"])
        return saved

    def content_fingerprint(self, judgment, text):
        links = list(
            CitationLink.objects.filter(document=judgment)
            .order_by("url", "text")
            .values_list("url", "text")
        )
        case_numbers = list(
            judgment.case_numbers.order_by("string").values_list("string", flat=True)
        )
        value = json.dumps(
            {
                "text": text,
                "case_name": judgment.case_name,
                "mnc": judgment.mnc,
                "date": judgment.date.isoformat(),
                "court": judgment.court_id,
                "case_numbers": case_numbers,
                "links": links,
                "pipeline": PIPELINE_VERSION,
            },
            sort_keys=True,
        )
        return hashlib.sha256(value.encode()).hexdigest()

    def find_matches(self, judgment, text):
        matches = {}

        # Candidate retrieval is intentionally exact and cheap. The more nuanced
        # procedural and court checks happen later in evaluate().
        for citation_match in NEUTRAL_CITATION_RE.finditer(text):
            citation = compact(citation_match.group(0))
            targets = Judgment.objects.filter(mnc__iexact=citation).select_related(
                "court", "court__court_class", "work"
            )
            for target in targets:
                self.add_match(
                    matches, target, "neutral_citation", citation_match.start()
                )

        for link in CitationLink.objects.filter(document=judgment):
            target_uri = urlparse(link.url).path.rstrip("/")
            targets = Judgment.objects.filter(
                Q(work_frbr_uri=target_uri) | Q(expression_frbr_uri=target_uri)
            ).select_related("court", "court__court_class", "work")
            position = text.find(compact(link.text)) if link.text else -1
            for target in targets:
                self.add_match(matches, target, "citation_link", max(position, 0))

        for case_match in CASE_NUMBER_RE.finditer(text):
            normalized = normalize_case_number(case_match.group(1))
            possible_numbers = CaseNumber.objects.filter(
                document__date__lt=judgment.date
            ).select_related(
                "document",
                "document__court",
                "document__court__court_class",
                "document__work",
            )
            for case_number in possible_numbers.filter(
                string__iexact=compact(case_match.group(1))
            )[:20]:
                if normalize_case_number(case_number.string) == normalized:
                    self.add_match(
                        matches,
                        case_number.document,
                        "case_number",
                        case_match.start(),
                    )

        signature = party_tokens(judgment.case_name or judgment.title)
        relationship_type, relationship_match = relationship_in(text[:30_000])
        if relationship_type and relationship_match and len(signature) >= 2:
            anchor = max(signature, key=len)
            possible = (
                Judgment.objects.filter(
                    date__lt=judgment.date,
                    case_name__icontains=anchor,
                )
                .exclude(pk=judgment.pk)
                .select_related("court", "court__court_class", "work")[:200]
            )
            exact = [
                target
                for target in possible
                if party_tokens(target.case_name or target.title) == signature
            ]
            if len(exact) <= 12:
                # Repeated litigation between the same parties may contain many
                # stages. The most recent earlier judgment from each court is the
                # safest deterministic approximation of the immediate predecessor.
                latest_by_court = {}
                for target in exact:
                    current = latest_by_court.get(target.court_id)
                    if current is None or target.date > current.date:
                        latest_by_court[target.court_id] = target
                for target in latest_by_court.values():
                    self.add_match(
                        matches,
                        target,
                        "party_signature",
                        relationship_match.start(),
                    )
        return matches

    def add_match(self, matches, target, method, position):
        match = matches.setdefault(target.pk, CandidateMatch(target))
        match.methods.add(method)
        match.positions.append(position)

    def evaluate(self, judgment, match, text, fingerprint):
        target = match.historical_judgment
        if target.pk == judgment.pk or target.date >= judgment.date:
            return None
        if CaseHistory.objects.filter(
            judgment_work=judgment.work,
            historical_judgment_work=target.work,
        ).exists():
            return None

        source_tokens = party_tokens(judgment.case_name or judgment.title)
        target_tokens = party_tokens(target.case_name or target.title)
        overlap = party_overlap(source_tokens, target_tokens)
        opening_relationship, opening_match = relationship_in(text[:30_000])

        best = None
        # A citation can appear several times. Use the occurrence closest to
        # procedural-history language and retain that passage as editor evidence.
        for position in match.positions:
            context_start = max(0, position - 750)
            context = text[context_start : min(len(text), position + 750)]
            relationship_type, relationship_match, distance = nearest_relationship(
                context, position - context_start
            )
            relationship_type = relationship_type or opening_relationship
            if not relationship_type:
                continue
            candidate = (
                distance if distance is not None else 100_000,
                position,
                context,
                relationship_type,
            )
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best is None:
            return None

        distance, position, context, relationship_type = best
        distance = None if distance == 100_000 else distance
        local_relationship = distance is not None
        local_label = bool(JUDGMENT_LABEL_RE.search(context))
        authority_marker = bool(AUTHORITY_MARKER_RE.search(context))
        same_court = target.court_id == judgment.court_id
        court_mentioned = self.target_court_mentioned(target, context)

        if relationship_type in {
            CaseHistorySuggestion.RelationshipType.APPEAL_FROM,
            CaseHistorySuggestion.RelationshipType.LEAVE_TO_APPEAL_FROM,
        }:
            if judgment.court.code == "ZASCA" and target.court.code == "ZACC":
                return None
            if overlap < 0.15 or not (court_mentioned or local_label):
                return None
            if same_court and not (
                "case_number" in match.methods
                or (
                    local_relationship
                    and distance <= 250
                    and local_label
                    and overlap >= 0.3
                )
            ):
                return None

        # These asymmetric checks remove common false positives where a judgment
        # merely cites a higher-court authority rather than describing its own
        # procedural history.
        if (
            relationship_type
            in {
                CaseHistorySuggestion.RelationshipType.CONFIRMATION_OF,
                CaseHistorySuggestion.RelationshipType.REVIEW_OF,
            }
            and same_court
        ):
            return None
        if relationship_type == CaseHistorySuggestion.RelationshipType.RESCISSION_OF:
            if (
                not same_court
                or not local_relationship
                or distance > 250
                or overlap < 0.4
            ):
                return None
        if (
            relationship_type
            == CaseHistorySuggestion.RelationshipType.RELATED_PROCEEDING
            and overlap == 0
        ):
            return None
        if "party_signature" in match.methods and not court_mentioned:
            return None

        source_class = getattr(judgment.court.court_class, "name", "")
        target_class = getattr(target.court.court_class, "name", "")
        if (
            source_class != "Apex Courts"
            and target_class == "Apex Courts"
            and relationship_type
            in {
                CaseHistorySuggestion.RelationshipType.APPEAL_FROM,
                CaseHistorySuggestion.RelationshipType.LEAVE_TO_APPEAL_FROM,
                CaseHistorySuggestion.RelationshipType.CONFIRMATION_OF,
                CaseHistorySuggestion.RelationshipType.REVIEW_OF,
            }
        ):
            return None

        # Scoring combines independent identifiers, local procedural language,
        # party continuity, court context and chronological direction. The raw
        # score remains visible so thresholds can be calibrated from editor data.
        score = 0
        if local_relationship:
            score += 5
            if distance <= 250:
                score += 3
            elif distance > 550:
                score -= 2
        if local_label:
            score += 3
        if opening_match:
            score += 2
        if "neutral_citation" in match.methods:
            score += 4
        if "citation_link" in match.methods:
            score += 3
        if "case_number" in match.methods:
            score += 1
        if "party_signature" in match.methods:
            score += 3
        if overlap >= 0.5:
            score += 4
        elif overlap >= 0.3:
            score += 3
        elif overlap >= 0.15:
            score += 2
        elif overlap > 0:
            score += 1
        else:
            score -= 2
        score += 2  # target predates source
        if not same_court:
            score += 1
        if court_mentioned:
            score += 2
        if position < 20_000:
            score += 1
        if authority_marker and not local_label:
            score -= 2
        if not local_relationship and overlap < 0.2:
            return None

        confidence = self.confidence(score)
        disposition = self.disposition(
            score,
            confidence,
            match.methods,
            overlap,
            court_mentioned,
            local_relationship,
            distance,
            relationship_type,
        )
        return {
            "relationship_type": relationship_type,
            "confidence": confidence,
            "score": score,
            "disposition": disposition,
            "matching_methods": sorted(match.methods),
            "signals": {
                "party_overlap": round(overlap, 4),
                "local_relationship_phrase": local_relationship,
                "relationship_distance": distance,
                "opening_relationship_phrase": bool(opening_match),
                "judgment_label_near_reference": local_label,
                "same_court": same_court,
                "target_court_mentioned": court_mentioned,
                "authority_language_near_reference": authority_marker,
            },
            "evidence": compact(context)[:1800],
            "evidence_position": position,
            "content_fingerprint": fingerprint,
        }

    def target_court_mentioned(self, target, value):
        value = value.lower()
        code = (target.court.code or "").lower()
        name = (target.court.name or "").lower()
        if code and re.search(rf"\b{re.escape(code)}\b", value):
            return True
        if name and name in value:
            return True
        aliases = {
            "zasca": ("supreme court of appeal", "sca"),
            "zacc": ("constitutional court",),
            "zalac": ("labour appeal court",),
        }
        return any(alias in value for alias in aliases.get(code, ()))

    def confidence(self, score):
        if score >= 24:
            return CaseHistorySuggestion.Confidence.HIGH
        if score >= 18:
            return CaseHistorySuggestion.Confidence.MEDIUM
        return CaseHistorySuggestion.Confidence.LOW

    def disposition(
        self,
        score,
        confidence,
        methods,
        overlap,
        court_mentioned,
        local_relationship,
        distance,
        relationship_type,
    ):
        if confidence == CaseHistorySuggestion.Confidence.LOW:
            return CaseHistorySuggestion.Disposition.REJECT
        if score >= 24 and overlap >= 0.3:
            return CaseHistorySuggestion.Disposition.AUTO_ACCEPT
        if (
            "party_signature" in methods
            and score >= 21
            and overlap >= 0.75
            and court_mentioned
            and relationship_type
            != CaseHistorySuggestion.RelationshipType.RELATED_PROCEEDING
        ):
            return CaseHistorySuggestion.Disposition.AUTO_ACCEPT
        if (
            {"neutral_citation", "citation_link"} <= methods
            and score >= 18
            and overlap >= 0.75
        ):
            return CaseHistorySuggestion.Disposition.AUTO_ACCEPT
        if (
            "case_number" in methods
            and local_relationship
            and distance is not None
            and distance <= 250
            and overlap >= 0.4
            and relationship_type
            in {
                CaseHistorySuggestion.RelationshipType.LEAVE_TO_APPEAL_FROM,
                CaseHistorySuggestion.RelationshipType.RESCISSION_OF,
            }
        ):
            return CaseHistorySuggestion.Disposition.AUTO_ACCEPT
        return CaseHistorySuggestion.Disposition.REVIEW
