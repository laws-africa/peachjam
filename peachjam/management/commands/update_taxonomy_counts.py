from django.core.management.base import BaseCommand

from peachjam.models.settings import pj_settings
from peachjam.models.taxonomies import TaxonomyDocumentCount


class Command(BaseCommand):
    help = "Recalculate pre-computed document counts for the flynote taxonomy tree."

    def handle(self, *args, **options):
        root = pj_settings().flynote_taxonomy_root
        if not root:
            self.stderr.write(
                self.style.ERROR(
                    "No flynote_taxonomy_root configured in Site Settings. "
                    "Set it in Django Admin before running this command."
                )
            )
            return

        self.stdout.write(
            f"Refreshing document counts for taxonomy root: {root.name} (pk={root.pk})"
        )
        TaxonomyDocumentCount.refresh_for_taxonomy(root)
        total = TaxonomyDocumentCount.objects.filter(
            taxonomy__path__startswith=root.path
        ).count()
        self.stdout.write(
            self.style.SUCCESS(f"Done. Updated counts for {total} taxonomy nodes.")
        )
