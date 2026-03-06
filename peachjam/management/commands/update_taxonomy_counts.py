import time

from django.core.management.base import BaseCommand

from peachjam.models.flynote import Flynote, FlynoteDocumentCount


class Command(BaseCommand):
    help = "Recalculate pre-computed document counts for the flynote tree."

    def handle(self, *args, **options):
        roots = Flynote.get_root_nodes()
        if not roots.exists():
            self.stderr.write(
                self.style.ERROR(
                    "No top-level flynotes found. Run update_flynote_taxonomies first."
                )
            )
            return

        self.stdout.write("Refreshing document counts for all flynotes...")
        start = time.time()
        FlynoteDocumentCount.refresh_for_flynote(None)
        elapsed = time.time() - start
        total = FlynoteDocumentCount.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Updated counts for {total} flynote nodes in {elapsed:.1f}s."
            )
        )
