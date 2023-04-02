from django.core.management import BaseCommand

from peachjam.graph.ranker import GraphRanker


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        GraphRanker().rank_and_publish()
