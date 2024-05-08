from django.core.management.base import BaseCommand

from peachjam_search.models import SearchTrace


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--days",
            default=90,
            type=int,
            help="Prune traces older than DAYS days",
        )

    def handle(self, *args, **options):
        SearchTrace.prune(options["days"])
