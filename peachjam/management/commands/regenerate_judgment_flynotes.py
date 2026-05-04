from django.core.management.base import BaseCommand
from django.db.models import Q

from peachjam.models import Judgment


class Command(BaseCommand):
    help = (
        "Find judgments whose flynotes contain a marker and regenerate their "
        "summaries using the standard summary-generation flow."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--contains",
            default=":[",
            help="Only match judgments whose flynote or flynote_raw contains this string.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most N matching judgments (0 = all).",
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
            "--dry-run",
            action="store_true",
            default=False,
            help="Only list matching judgments without regenerating summaries.",
        )

    def handle(self, *args, **options):
        marker = options["contains"]
        dry_run = options["dry_run"]

        qs = (
            Judgment.objects.filter(
                Q(flynote__contains=marker) | Q(flynote_raw__contains=marker)
            )
            .order_by("-pk")
            .only(
                "pk",
                "case_name",
                "expression_frbr_uri",
                "case_summary",
                "summary_ai_generated",
                "must_be_anonymised",
                "anonymised",
            )
        )

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
            self.stdout.write(f"Processing all {total} matching judgments...")

        if options["start_id"]:
            self.stdout.write(f"Starting from judgment pk={options['start_id']}")

        if dry_run:
            self.stdout.write(
                "Listing matches only. Re-run without --dry-run to regenerate summaries."
            )
        else:
            self.stdout.write("Regenerating summaries now.")

        processed = 0
        eligible = 0
        regenerated = 0
        skipped = 0
        last_pk = None

        for judgment in qs.iterator():
            processed += 1
            last_pk = judgment.pk
            reason = self.skip_reason(judgment)
            status = "regenerate" if reason is None else f"skip ({reason})"
            self.stdout.write(
                f"  [{processed}] (pk={judgment.pk}) {status} {judgment.case_name}"
            )

            if reason is not None:
                skipped += 1
                continue

            eligible += 1
            if not dry_run:
                judgment.track_changes()
                judgment.generate_summary()
                regenerated += 1

        msg = f"Done. Matched {processed} judgments."
        if dry_run:
            msg += f" Eligible to regenerate: {eligible}."
        else:
            msg += f" Regenerated {regenerated} judgment summary(s)."
        if skipped:
            msg += f" Skipped {skipped} ineligible judgment(s)."
        if last_pk:
            msg += f" Last pk processed: {last_pk}."

        self.stdout.write(self.style.SUCCESS(msg))

    def skip_reason(self, judgment):
        if judgment.must_be_anonymised and not judgment.anonymised:
            return "awaiting anonymisation"

        if judgment.case_summary and not judgment.summary_ai_generated:
            return "human summary"

        return None
