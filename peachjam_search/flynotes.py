"""Flynote topic suggestions for document search results."""

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


class FlynoteSearchMatcher:
    """Find direct flynote matches, then fill gaps from ranked judgments."""

    direct_match_limit = 2
    result_limit = 3
    top_judgment_limit = 10
    minimum_document_count = 2

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

        Direct name matches are preferred because they are explicit. The
        remaining slots are filled with topics supported by the highest ranked
        judgment results, which covers queries that use different language to
        the flynote taxonomy.
        """
        direct_matches = self.direct_matches(query)
        selected = self.select_distinct_branches(
            direct_matches, self.direct_match_limit
        )

        if len(selected) < self.result_limit:
            # A textual match alone misses equivalent legal language, so use
            # the judgments already ranked by Elasticsearch to fill the gaps.
            fallback_matches = self.topics_from_search_hits(search_hits)
            selected.extend(
                self.select_distinct_branches(
                    fallback_matches,
                    self.result_limit - len(selected),
                    selected,
                )
            )

        path_labels = Flynote.get_path_labels(selected)
        direct_ids = {flynote.pk for flynote in direct_matches}
        return [
            FlynoteSearchHit(
                flynote=flynote,
                count=flynote.doc_count,
                path_labels=path_labels.get(flynote.pk, []),
                source=(
                    "direct_query" if flynote.pk in direct_ids else "document_support"
                ),
            )
            for flynote in selected
        ]

    def direct_matches(self, query):
        query = (query or "").strip()
        if not query:
            return []

        return list(
            self.with_document_counts(
                Flynote.objects.undeprecated().filter(name__icontains=query)
            )
            .filter(doc_count__gte=self.minimum_document_count)
            .order_by("-doc_count", "-depth", "name")
        )

    def topics_from_search_hits(self, search_hits):
        # SearchHit.position is one-based and reflects the result order. Keep
        # it so that a topic supported by earlier judgments ranks more highly.
        positions = {
            hit.id: hit.position
            for hit in search_hits[: self.top_judgment_limit]
            if getattr(hit, "document", None)
        }
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
                    supporting_documents[path].add(link.document_id)

        def ranking_key(item):
            path, document_ids = item
            flynote = flynotes_by_path[path]
            # Reciprocal position weighting makes support from the first
            # result matter more than support from the tenth. The remaining
            # fields provide stable, useful tie-breakers.
            rank_support = sum(
                1 / positions[document_id] for document_id in document_ids
            )
            return (
                -rank_support,
                -len(document_ids),
                -flynote.depth,
                -flynote.doc_count,
                flynote.name,
            )

        return [
            flynotes_by_path[path]
            for path, _ in sorted(supporting_documents.items(), key=ranking_key)
        ]

    @staticmethod
    def select_distinct_branches(candidates, limit, selected=()):
        selected = list(selected)
        selected_ids = {flynote.pk for flynote in selected}
        chosen = []
        for candidate in candidates:
            if candidate.pk in selected_ids:
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
            chosen.append(candidate)
            if len(chosen) >= limit:
                break
        return chosen
