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

        FlynoteDocumentCount.refresh_for_flynote(None)
        self.stdout.write(self.style.SUCCESS("Done."))
