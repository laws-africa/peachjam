from argparse import BooleanOptionalAction

from django.core.management.base import BaseCommand

from peachjam.analysis.flynotes import FlynoteUpdater
from peachjam.models import Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount


class Command(BaseCommand):
    help = "Parse flynote text on judgments and sync Flynote nodes and links."

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
        parser.add_argument(
            "--start-id",
            type=int,
            default=None,
            help="Start processing from this judgment PK downwards (useful for resuming after a failure).",
        )
        parser.add_argument(
            "--skip-counts",
            action="store_true",
            default=False,
            help="Skip refreshing flynote document counts entirely. "
            "Useful in batch mode when counts will be updated separately.",
        )
        parser.add_argument(
            "--assume-clean",
            action=BooleanOptionalAction,
            default=True,
            help="Treat no-semicolon flynotes as already well-structured dash chains.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Using Flynote model (no taxonomy root required)")

        updater = FlynoteUpdater(assume_clean=options["assume_clean"])
        skip_counts = options["skip_counts"]

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
            affected_root_ids = updater.update_for_judgment(judgment)
            if not skip_counts:
                for root in (
                    Flynote.get_root_nodes()
                    .filter(pk__in=set(affected_root_ids))
                    .order_by("path")
                ):
                    FlynoteDocumentCount.refresh_for_flynote(root)
            self.stdout.write(self.style.SUCCESS("Done."))
            return

        qs = (
            Judgment.objects.exclude(flynote_raw__isnull=True)
            .exclude(flynote_raw="")
            .order_by("-pk")
        )

        if options["start_id"]:
            qs = qs.filter(pk__lte=options["start_id"])

        total = qs.count()

        if options["limit"]:
            qs = qs[: options["limit"]]
            self.stdout.write(
                f"Processing {options['limit']} of {total} judgments with flynotes..."
            )
        else:
            self.stdout.write(f"Processing all {total} judgments with flynotes...")

        if options["start_id"]:
            self.stdout.write(f"Starting from judgment pk={options['start_id']}")

        if skip_counts:
            self.stdout.write("Skipping flynote count updates.")

        processed = 0
        skipped = 0
        last_pk = None
        affected_root_ids = set()
        for judgment in qs.iterator():
            processed += 1
            last_pk = judgment.pk
            self.stdout.write(
                f"  [{processed}] (pk={judgment.pk}) {judgment.case_name}"
            )
            try:
                affected_root_ids.update(updater.update_for_judgment(judgment))
            except Exception as e:
                skipped += 1
                self.stderr.write(
                    self.style.WARNING(f"    Skipped (pk={judgment.pk}): {e}")
                )

        msg = f"Done. Processed {processed} judgments."
        if skipped:
            msg += f" Skipped {skipped} due to errors."
        if last_pk:
            msg += f" Last pk processed: {last_pk}."

        if not skip_counts and affected_root_ids:
            for root in (
                Flynote.get_root_nodes()
                .filter(pk__in=set(affected_root_ids))
                .order_by("path")
            ):
                FlynoteDocumentCount.refresh_for_flynote(root)
            msg += " Flynote counts refreshed."

        self.stdout.write(self.style.SUCCESS(msg))
