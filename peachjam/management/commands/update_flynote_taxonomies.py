from django.core.management.base import BaseCommand

from peachjam.analysis.flynotes import FlynoteTaxonomyUpdater
from peachjam.models import Judgment
from peachjam.models.settings import pj_settings


class Command(BaseCommand):
    help = "Parse flynote text on judgments and sync taxonomy nodes and links."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N judgments (0 = all).",
        )
        parser.add_argument(
            "--judgment-id",
            type=int,
            default=None,
            help="Process a single judgment by primary key.",
        )

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

        self.stdout.write(f"Using taxonomy root: {root.name} (pk={root.pk})")

        updater = FlynoteTaxonomyUpdater()

        if options["judgment_id"]:
            judgment = Judgment.objects.filter(pk=options["judgment_id"]).first()
            if not judgment:
                self.stderr.write(
                    self.style.ERROR(
                        f"Judgment with pk={options['judgment_id']} not found."
                    )
                )
                return
            self.stdout.write(f"Processing: {judgment.case_name}")
            updater.update_for_judgment(judgment)
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        qs = (
            Judgment.objects.exclude(flynote__isnull=True)
            .exclude(flynote="")
            .order_by("-pk")
        )
        total = qs.count()

        if options["limit"]:
            qs = qs[: options["limit"]]
            self.stdout.write(
                f"Processing {options['limit']} of {total} judgments with flynotes..."
            )
        else:
            self.stdout.write(f"Processing all {total} judgments with flynotes...")

        processed = 0
        skipped = 0
        for judgment in qs.iterator():
            processed += 1
            self.stdout.write(f"  [{processed}] {judgment.case_name}")
            try:
                updater.update_for_judgment(judgment)
            except Exception as e:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(f"    Skipped (pk={judgment.pk}): {e}")
                )

        msg = f"Done. Processed {processed} judgments."
        if skipped:
            msg += f" Skipped {skipped} due to errors."
        self.stdout.write(self.style.SUCCESS(msg))
