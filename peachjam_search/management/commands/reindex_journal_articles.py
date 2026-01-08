from django.core.management.base import BaseCommand

from peachjam.models import JournalArticle
from peachjam_search.tasks import search_model_saved


class Command(BaseCommand):
    help = "Queue reindexing tasks for all journal articles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Chunk size for iterating through journal article PKs.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        qs = JournalArticle.objects.order_by("pk").values_list("pk", flat=True)

        count = 0
        for pk in qs.iterator(chunk_size=batch_size):
            search_model_saved("peachjam.JournalArticle", pk)
            count += 1

        self.stdout.write(f"Queued reindexing for {count} journal articles.")
