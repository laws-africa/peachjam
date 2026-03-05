from django.core.management.base import BaseCommand

from peachjam.models.flynote import Flynote, FlynoteDocumentCount


class Command(BaseCommand):
    help = "Recalculate pre-computed document counts for the flynote tree."

    def handle(self, *args, **options):
        roots = Flynote.objects.filter(depth=0)
        if not roots.exists():
            self.stderr.write(
                self.style.ERROR(
                    "No top-level flynotes found. Run update_flynote_taxonomies first."
                )
            )
            return

        for root in roots:
            self.stdout.write(
                f"Refreshing document counts for flynote: {root.name} (pk={root.pk})"
            )
            FlynoteDocumentCount.refresh_for_flynote(root)

        total = FlynoteDocumentCount.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Done. Updated counts for {total} flynote nodes.")
        )
