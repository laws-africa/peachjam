"""Flynote topic suggestions for document search results."""

import re
from collections import defaultdict
from dataclasses import dataclass

from django.db.models import F, IntegerField, Value
from django.db.models.functions import Coalesce

from peachjam.models.flynote import Flynote, JudgmentFlynote


@dataclass(frozen=True)
class FlynoteSearchHit:
    flynote: Flynote
    count: int
    path_labels: list[str]
    source: str
    selection_reason: str
    result_id: str | None = None


@dataclass(frozen=True)
class FlynoteSearchCandidate:
    flynote: Flynote
    selection_reason: str


class FlynoteSearchMatcher:
    """Find direct flynote matches, then fill gaps from ranked judgments."""

    result_limit = 3
    top_judgment_limit = 10
    minimum_document_count = 2
    minimum_fallback_document_support = 2
    minimum_convergent_document_support = 3
    minimum_convergent_rank_support = 1.0
    fallback_stop_words = frozenset(
        {"a", "an", "and", "for", "in", "of", "on", "the", "to", "under", "with"}
    )

    @staticmethod
    def with_document_counts(queryset):
        return queryset.annotate(
            doc_count=Coalesce(
                F("document_count_cache__count"),
                Value(0),
                output_field=IntegerField(),
            )
        )

    def match(self, query, search_hits):
        """Return up to three distinct, eligible topic suggestions.

        Direct name matches are preferred because they are explicit. Topics
        supported by the highest-ranked judgments only fill any remaining
        card slots, which covers queries that use different language to the
        flynote taxonomy.
        """
        direct_matches = self.direct_matches(query)
        selected = self.select_distinct_branches(direct_matches, self.result_limit)
        selected_sources = {flynote.pk: "direct_query" for flynote in selected}
        selection_reasons = {flynote.pk: "direct_name_match" for flynote in selected}

        if len(selected) < self.result_limit:
            # Direct topic-name matches are the most trustworthy suggestions.
            # Document-supported topics can supplement them, but never replace
            # them or exceed the three-card limit.
            fallback_matches = self.topics_from_search_hits(query, search_hits)
            fallback_selected = self.select_distinct_branches(
                [candidate.flynote for candidate in fallback_matches],
                self.result_limit - len(selected),
                selected,
            )
            selected.extend(fallback_selected)
            selected_sources.update(
                (flynote.pk, "document_support") for flynote in fallback_selected
            )
            selection_reasons.update(
                {
                    candidate.flynote.pk: candidate.selection_reason
                    for candidate in fallback_matches
                    if candidate.flynote in fallback_selected
                }
            )

        path_labels = Flynote.get_path_labels(selected)
        return [
            FlynoteSearchHit(
                flynote=flynote,
                count=flynote.doc_count,
                path_labels=path_labels.get(flynote.pk, []),
                source=selected_sources[flynote.pk],
                selection_reason=selection_reasons[flynote.pk],
            )
            for flynote in selected
        ]

    def direct_matches(self, query):
        query = (query or "").strip()
        if not query:
            return []

        return list(
            self.with_document_counts(Flynote.objects.matching_names(query))
            .filter(doc_count__gte=self.minimum_document_count)
            .order_by("-doc_count", "-depth", "name")
        )

    def topics_from_search_hits(self, query, search_hits):
        # SearchHit.position is one-based and reflects the result order. Keep
        # it so that a topic supported by earlier judgments ranks more highly.
        positions = {}
        document_work_keys = {}
        work_positions = {}
        for hit in search_hits[: self.top_judgment_limit]:
            document = getattr(hit, "document", None)
            if not document:
                continue

            positions[hit.id] = hit.position
            # Search can return multiple expressions of one judgment. They
            # should count as one supporting judgment, using the earliest
            # expression's result position for its rank contribution.
            work_key = document.work_frbr_uri or hit.id
            document_work_keys[hit.id] = work_key
            work_positions[work_key] = min(
                hit.position, work_positions.get(work_key, hit.position)
            )
        if not positions:
            return []

        links = list(
            JudgmentFlynote.objects.filter(document_id__in=positions)
            .select_related("flynote")
            .only("document_id", "flynote__path")
        )
        if not links:
            return []

        ancestor_paths = set()
        for link in links:
            leaf = link.flynote
            # JudgmentFlynote records the leaf only. Treebeard's materialised
            # path makes it cheap to add every ancestor as a possible topic.
            ancestor_paths.update(
                leaf.path[:end]
                for end in range(leaf.steplen, len(leaf.path) + 1, leaf.steplen)
            )

        flynotes_by_path = {
            flynote.path: flynote
            for flynote in self.with_document_counts(
                Flynote.objects.undeprecated().filter(
                    path__in=ancestor_paths,
                    # Root nodes are broad areas of law. They remain eligible
                    # for explicit query matches, but not inferred suggestions.
                    depth__gt=1,
                )
            ).filter(doc_count__gte=self.minimum_document_count)
        }
        supporting_documents = defaultdict(set)
        for link in links:
            leaf = link.flynote
            for end in range(leaf.steplen, len(leaf.path) + 1, leaf.steplen):
                path = leaf.path[:end]
                if path in flynotes_by_path:
                    # A judgment can have several leaf paths below one topic;
                    # it must still provide only one vote for that topic.
                    supporting_documents[path].add(document_work_keys[link.document_id])

        def ranking_key(item):
            path, document_ids = item
            flynote = flynotes_by_path[path]
            # Reciprocal position weighting makes support from the first
            # result matter more than support from the tenth. The remaining
            # fields provide stable, useful tie-breakers.
            rank_support = sum(
                1 / work_positions[work_key] for work_key in document_ids
            )
            return (
                -rank_support,
                -len(document_ids),
                -flynote.depth,
                -flynote.doc_count,
                flynote.name,
            )

        eligible_candidates = []
        for path, document_ids in supporting_documents.items():
            flynote = flynotes_by_path[path]
            rank_support = sum(
                1 / work_positions[work_key] for work_key in document_ids
            )
            lexical_match = self.fallback_topic_matches_query(flynote.name, query)
            normal_support = (
                lexical_match
                and len(document_ids) >= self.minimum_fallback_document_support
            )
            # Several independent judgments near the top of the results are
            # strong evidence that a topic is relevant even where its label
            # uses different wording from the query. This is deliberately
            # stricter than the ordinary lexical-match path.
            strong_convergence = (
                len(document_ids) >= self.minimum_convergent_document_support
                and rank_support >= self.minimum_convergent_rank_support
            )
            if normal_support or strong_convergence:
                eligible_candidates.append((path, document_ids))
        candidates = []
        for path, document_ids in sorted(eligible_candidates, key=ranking_key):
            flynote = flynotes_by_path[path]
            if (
                self.fallback_topic_matches_query(flynote.name, query)
                and len(document_ids) >= self.minimum_fallback_document_support
            ):
                selection_reason = "lexical_document_support"
            else:
                selection_reason = "strong_document_convergence"
            candidates.append(FlynoteSearchCandidate(flynote, selection_reason))
        return candidates

    def fallback_topic_matches_query(self, topic_name, query):
        """Require fallback topics to share a meaningful query word.

        Document support alone only tells us that a topic was attached to a
        relevant judgment. It does not make every topic on that judgment a
        suitable recommendation. Until flynotes have their own semantic index,
        this lexical anchor avoids surfacing unrelated procedural topics.
        """
        query_words = {
            word
            for word in re.findall(r"\w+", (query or "").casefold())
            if len(word) > 2 and word not in self.fallback_stop_words
        }
        topic_words = set(re.findall(r"\w+", topic_name.casefold()))
        return bool(query_words & topic_words)

    @staticmethod
    def select_distinct_branches(candidates, limit, selected=()):
        selected = list(selected)
        selected_ids = {flynote.pk for flynote in selected}
        selected_names = {flynote.name.casefold() for flynote in selected}
        chosen = []
        for candidate in candidates:
            if (
                candidate.pk in selected_ids
                # Topic names from different taxonomy branches are often
                # duplicates. The breadcrumb is helpful context, but several
                # cards with the same heading make the result feel repetitive.
                or candidate.name.casefold() in selected_names
            ):
                continue
            # Do not display both a topic and one of its descendants; this is
            # the practical form of the no-duplicate-branch rule for cards.
            if any(
                candidate.path.startswith(flynote.path)
                or flynote.path.startswith(candidate.path)
                for flynote in selected
            ):
                continue
            selected.append(candidate)
            selected_ids.add(candidate.pk)
            selected_names.add(candidate.name.casefold())
            chosen.append(candidate)
            if len(chosen) >= limit:
                break
        return chosen
