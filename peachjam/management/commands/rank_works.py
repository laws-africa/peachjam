from django.core.management import BaseCommand

from peachjam.analysis.ranker import GraphRanker


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update of rankings",
        )

    def handle(self, *args, **options):
        GraphRanker(force_update=options["force"]).rank_and_publish()
