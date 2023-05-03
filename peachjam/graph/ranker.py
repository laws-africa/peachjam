import logging

from graphdatascience import GraphDataScience
from neomodel import db

from ..models import ExtractedCitation, Work
from .models import Work as NeoWork

# from neomodel.core import install_labels


log = logging.getLogger(__name__)


class GraphRanker:
    """Reads and writes ranks for works based on graph weights using neo4j's ArticleRank algorithm, which is similar
    to PageRank.

    See: https://neo4j.com/docs/graph-data-science/current/algorithms/article-rank/
    """

    def rank_and_publish(self):
        self.populate_graph()
        self.calculate_ranks()
        self.publish_ranks()

    def populate_graph(self):
        """Build the graph database from our database."""
        citations = ExtractedCitation.objects.prefetch_related(
            "citing_work", "target_work"
        ).all()

        # reset the db
        log.info("Deleting old graph")
        for node in NeoWork.nodes.all():
            node.delete()

        # create the works
        log.info("Creating new graph")
        works = {c.citing_work for c in citations} | {c.target_work for c in citations}
        neo_works = NeoWork.create_or_update(*[{"frbr_uri": w.frbr_uri} for w in works])

        # setup constraints and indexes -- disabled because v 4 of the library doesn't support the new 5.x server syntax
        # install_labels(NeoWork)

        # index the nodes
        neo_works = {w.frbr_uri: w for w in neo_works}

        # create the relationships
        for citation in citations:
            citing = neo_works[citation.citing_work.frbr_uri]
            target = neo_works[citation.target_work.frbr_uri]
            citing.cites.connect(target)

        log.info("Graph populated")

    def calculate_ranks(self):
        """Run articlerank and update the "rank" property on the graph nodes."""
        gds = GraphDataScience(db.driver)

        # project the graph
        log.info("Projecting graph")
        graph = gds.graph.project("citations", "Work", "CITES")[0]

        log.info("Running articlerank")
        res = gds.articleRank.write(graph, writeProperty="rank", scaler="L1NORM")
        if not res.didConverge:
            raise Exception(f"articleRank did not converge: {res}")
        log.info("Finished articlerank")

        # clean up
        graph.drop()

    def publish_ranks(self):
        """Store ranks for each work."""
        # TODO: only update those that have changed
        # TODO: update elasticsearch directly?
        works = {w.frbr_uri: w for w in Work.objects.all()}

        for neo_work in NeoWork.nodes.all():
            work = works[neo_work.frbr_uri]
            work.ranking = neo_work.ranking
            work.save(update_fields=["ranking"])
