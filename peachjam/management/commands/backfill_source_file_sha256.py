from django.core.management.base import BaseCommand

from peachjam.models import CoreDocument, SourceFile


class Command(BaseCommand):
    help = "Backfill sha256 for all SourceFile objects that don't have it"

    def add_arguments(self, parser):
        choices = " ".join(x for x, y in CoreDocument.DOC_TYPE_CHOICES)
        parser.add_argument(
            "--doctype",
            type=str,
            help=f"Limit to document types (comma-separated): {choices}",
        )

    def handle(self, *args, **kwargs):
        source_files = SourceFile.objects.filter(sha256__isnull=True)

        doctypes = kwargs.get("doctype")
        if doctypes:
            doctypes = doctypes.split(",")
            source_files = source_files.filter(document__doc_type__in=doctypes)

        total = source_files.count()
        self.stdout.write(f"Found {total} SourceFile objects without sha256")

        for source_file in source_files.order_by("-id").iterator(100):
            try:
                source_file.calculate_sha256()
                source_file.save()
                self.stdout.write(f"Updated sha256 for SourceFile id {source_file.id}")
            except Exception as e:
                self.stderr.write(
                    f"Error updating sha256 for SourceFile id {source_file.id}: {e}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully backfilled sha256 for all SourceFile objects"
            )
        )
