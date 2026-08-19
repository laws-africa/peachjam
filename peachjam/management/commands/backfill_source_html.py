from django.core.management.base import BaseCommand
from django.db.models import F

from peachjam.models import DocumentContent


class Command(BaseCommand):
    help = (
        "Backfill DocumentContent.source_html from content_html for non-AKN documents "
        "where content_html was set directly, leaving source_html blank"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be updated without making changes",
        )

    def handle(self, *args, **kwargs):
        qs = DocumentContent.objects.filter(
            source_html__isnull=True,
            content_html__isnull=False,
            content_html_is_akn=False,
        )

        total = qs.count()
        self.stdout.write(
            f"Found {total} DocumentContent objects with content_html but no source_html"
        )

        if kwargs["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run, no changes made"))
            return

        # bulk update deliberately bypasses save hooks: content_html already holds the
        # derived value, so re-deriving it and re-extracting citations is unnecessary
        updated = qs.update(source_html=F("content_html"))

        self.stdout.write(
            self.style.SUCCESS(f"Backfilled source_html for {updated} documents")
        )
