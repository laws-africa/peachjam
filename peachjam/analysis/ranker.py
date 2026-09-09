import datetime
import logging
import math

import igraph as ig
from elasticsearch import helpers

from peachjam.models import CoreDocument, pj_settings
from peachjam_search.documents import MultiLanguageIndexManager, SearchableDocument

from ..models import ExtractedCitation

log = logging.getLogger(__name__)


class GraphRanker:
    """Calculates pagerank and other scores for works.

    * pagerank based on citation networks
    * normalized pagerank [0, 1]
    * log-normalized citation counts [0, 1]
    * weighted authority score

    Authority Score Calculation

    This system improves document ranking and recommendation quality by introducing
    an Authority Score, which measures a document’s importance within the citation network.

    The Authority Score combines three complementary signals:

    1. PageRank:
       - Computed using the PageRank algorithm on the document citation graph.
       - Measures influence: a document cited by highly influential documents receives a higher PageRank.
       - Captures both direct and indirect importance.

    2. Citation Count:
       - Counts how many documents cite the given document.
       - Measures raw popularity, independent of the quality of the citing documents.
       - Helps identify documents that are widely referenced even if by less influential sources.

    3. Recency score:
       - Recent documents are boosted slightly to account for the fact that they haven't had time to be cited yet.

    Normalization:
    - PageRank values are min-max normalized across the full corpus to scale to [0, 1].
    - Citation counts are log-transformed using log(1 + count) to reduce the effect of extreme outliers,
      and then min-max normalized to [0, 1].

    Combination:
    The final Authority Score is calculated as a weighted sum:
        authority_score = 0.6 * normalized_pagerank + 0.3 * normalized_log_citation_count + 0.1 * recency

    - PageRank is weighted more heavily to prioritize influence over popularity.
    - The weighting can be tuned based on empirical ranking quality.

    Purpose:
    - This blended score favors documents that are both influential and widely cited.
    - It reduces bias toward obscure but heavily cited documents or important but rarely cited ones.
    - It produces a more reliable and balanced authority signal for improving semantic search,
      related document suggestions, and content discovery.

    The Authority Score is precomputed and stored with document metadata, and later combined
    with other signals such as semantic similarity and document recency during re-ranking.
    """

    AUTHORITY_WEIGHT_PAGERANK = 0.7
    AUTHORITY_WEIGHT_CITATIONS = 0.3
    # TODO: this is turned off for now, it skews scores too much
    AUTHORITY_WEIGHT_RECENCY = 0.0

    # the maximum age of a document in days to be considered "recent"
    RECENCY_AGE_DAYS = 365

    work_ids = None
    graph = None
    ranks = None
    normalized_ranks = None
    normalized_n_citing_works = None
    authority_scores = None

    def __init__(self, force_update=False):
        self.force_update = force_update

    def rank_and_publish(self):
        self.populate_graph()
        self.calculate_ranks()
        self.publish_ranks()

    def populate_graph(self):
        """Build the graph database from our database."""
        citations = ExtractedCitation.objects.prefetch_related(
            "citing_work", "target_work"
        ).all()

        # create the works
        log.info("Creating graph")
        works = {c.citing_work for c in citations} | {c.target_work for c in citations}

        # igraph's vertices are 0-indexed, so we need to map our works to integers
        self.work_ids = {w: i for i, w in enumerate(works)}

        # it's fastest to add everything all at once
        edges = [
            (self.work_ids[c.citing_work], self.work_ids[c.target_work])
            for c in citations
        ]

        self.graph = ig.Graph(n=len(self.work_ids), edges=edges, directed=True)
        log.info("Created graph")

    def calculate_ranks(self):
        log.info("Running pagerank")
        self.ranks = self.graph.pagerank()
        log.info("Finished pagerank")

        # calculate normalised pageranks using min-max normalization to [0, 1]
        self.normalized_ranks = min_max_normalize(self.ranks)

        # calculate log-normal min/max normalised citation counts
        in_degrees = self.graph.degree(mode="in")
        self.normalized_n_citing_works = min_max_normalize(
            [math.log(x + 1) for x in in_degrees]
        )

        recency_scores = self.calculate_recency_scores()

        # calculate weighted authority scores
        self.authority_scores = [
            self.AUTHORITY_WEIGHT_PAGERANK * rank
            + self.AUTHORITY_WEIGHT_CITATIONS * citation_count
            + self.AUTHORITY_WEIGHT_RECENCY * recency
            for rank, citation_count, recency in zip(
                self.normalized_ranks, self.normalized_n_citing_works, recency_scores
            )
        ]

    def calculate_recency_scores(self):
        """Recency scores to compensate for recent documents that are too new to be cited.
        We use the earliest document date for each work."""
        dates = {
            x["work_id"]: x["date"]
            for x in CoreDocument.objects.filter(work__in=self.work_ids.keys())
            .values("work_id", "date")
            .distinct("work_id")
            .order_by("work_id", "date")
        }
        # build ordered list of dates for works
        dates = [dates.get(w.pk) for w in self.work_ids.keys()]
        today = datetime.date.today()
        ages = [(today - d).days if d else self.RECENCY_AGE_DAYS for d in dates]
        return [
            1 - (age / self.RECENCY_AGE_DAYS) if age < self.RECENCY_AGE_DAYS else 0
            for age in ages
        ]

    def publish_ranks(self):
        """Store ranks for each work."""
        # calculate the pivot as the geometric mean of the ranks
        ranks = [x for x in self.ranks if x > 0.0]
        if ranks:
            # analysis shows that the p99 is a good pivot
            # see https://colab.research.google.com/drive/1KlYC7A9JeqS_uaLhL8yv_IrAmHHXNCdK
            pivot = percentile(sorted(ranks), 0.99)
            log.info(f"Updating pagerank pivot (p99 of non-zero ranks): {pivot}")
            settings = pj_settings()
            settings.pagerank_pivot_value = pivot
            settings.save(update_fields=["pagerank_pivot_value"])

        log.info("Updating database")

        count = 0
        pagerank_changed = []
        for work, rank, norm_rank, citations, authority_score in zip(
            self.work_ids.keys(),
            self.ranks,
            self.normalized_ranks,
            self.normalized_n_citing_works,
            self.authority_scores,
        ):
            # these two are our key values
            if (
                self.force_update
                or work.pagerank != rank
                or work.authority_score != authority_score
            ):
                count += 1
                work.pagerank = rank
                work.pagerank_normalized = norm_rank
                work.n_citing_works_normalized = citations
                work.authority_score = authority_score
                work.save()
                if work.pagerank != rank:
                    pagerank_changed.append(work)

        log.info(f"Updated database with {count} works")
        self.update_elasticsearch(pagerank_changed)

    def update_elasticsearch(self, works):
        """use elasticsearch client to bulk update the "ranking" field on the provided docs"""
        docs = CoreDocument.objects.filter(work__in=works).values(
            "id", "work__pagerank", "language__iso_639_2T"
        )
        log.info(
            f"updating elasticsearch with {len(docs)} documents",
        )
        actions = (
            {
                "_op_type": "update",
                "_index": MultiLanguageIndexManager.get_instance().get_index_for_language(
                    doc["language__iso_639_2T"]
                ),
                "_id": doc["id"],
                "doc": {"ranking": doc["work__pagerank"]},
            }
            for doc in docs
        )
        helpers.bulk(
            SearchableDocument._index._get_connection(),
            actions,
            chunk_size=1000,
            request_timeout=60 * 60 * 30,
        )
        log.info("Updated elasticsearch")


def percentile(values, percent):
    """
    Find the percentile of a list of values.

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.

    @return - the percentile of the values
    """
    if not values:
        return None
    k = (len(values) - 1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return d0 + d1


def min_max_normalize(values):
    """Normalize a list of values to the range [0, 1]."""
    if not values:
        return []

    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [0.5] * len(values)
    diff = max_val - min_val
    return [(x - min_val) / diff for x in values]
