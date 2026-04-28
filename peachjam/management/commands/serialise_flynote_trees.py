from django.core.management.base import BaseCommand

from peachjam.models import Judgment


class Command(BaseCommand):
    help = "Serialise judgment flynote trees back into flynote and flynote_raw."

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

    def handle(self, *args, **options):
        qs = Judgment.objects.filter(flynotes__isnull=False).distinct().order_by("-pk")

        if options["judgment_id"]:
            qs = qs.filter(pk=options["judgment_id"])
            if not qs.exists():
                self.stderr.write(
                    self.style.ERROR(
                        f"Judgment with pk={options['judgment_id']} not found."
                    )
                )
                return

        if options["start_id"]:
            qs = qs.filter(pk__lte=options["start_id"])

        total = qs.count()

        if options["judgment_id"]:
            self.stdout.write(f"Processing judgment pk={options['judgment_id']}...")
        elif options["limit"]:
            qs = qs[: options["limit"]]
            self.stdout.write(f"Processing {options['limit']} of {total} judgments...")
        else:
            self.stdout.write(f"Processing all {total} judgments...")

        if options["start_id"]:
            self.stdout.write(f"Starting from judgment pk={options['start_id']}")

        processed = 0
        skipped = 0
        last_pk = None

        for judgment in qs.only("pk").iterator():
            processed += 1
            last_pk = judgment.pk
            self.stdout.write(
                f"  [{processed}] (pk={judgment.pk}) {judgment.case_name}"
            )
            try:
                judgment.serialise_flynote_tree()
                judgment.save(update_fields=["flynote", "flynote_raw"])
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

        self.stdout.write(self.style.SUCCESS(msg))
