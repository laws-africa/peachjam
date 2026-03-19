import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from peachjam.models import Judgment, Outcome
from peachjam.models.judgment import CaseHistory


class Command(BaseCommand):
    help = (
        "Create canonical outcomes from a CSV, relink judgments from bad outcomes "
        "to canonical outcomes, and update case histories. Does not delete old outcomes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            required=True,
            help=(
                "Path to the mapping CSV. "
                "Expected columns: ID, Name, canonical_outcomes"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run inside a transaction and roll back at the end.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        rows = self.load_rows(csv_path)
        canonical_names = sorted(
            {name for row in rows for name in row["canonical_names"] if name}
        )

        if not canonical_names:
            raise CommandError("No canonical outcomes found in CSV.")

        self.stdout.write(f"Loaded {len(rows)} mapping rows.")
        self.stdout.write(f"Found {len(canonical_names)} canonical outcomes.")

        with transaction.atomic():
            canonical_lookup, created_count = self.ensure_canonical_outcomes(
                canonical_names
            )

            summary = self.apply_mapping(rows, canonical_lookup)

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run complete, rolling back."))
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "Done.\n"
                f"Canonical outcomes created: {created_count}\n"
                f"Judgments updated: {summary['judgments_updated']}\n"
                f"Judgment links added: {summary['judgment_links_added']}\n"
                f"Judgment links removed: {summary['judgment_links_removed']}\n"
                f"Case histories updated: {summary['case_histories_updated']}\n"
                f"Rows skipped (unmapped): {summary['rows_skipped_unmapped']}\n"
                f"Rows skipped (missing bad outcome): {summary['rows_skipped_missing_bad']}\n"
                f"Rows skipped (identity rows): {summary['rows_skipped_identity']}"
            )
        )

    def load_rows(self, csv_path: Path):
        rows = []

        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            required = {"ID", "Name", "canonical_outcomes"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(
                    f"CSV must contain columns {sorted(required)}. "
                    f"Missing: {sorted(missing)}"
                )

            for row in reader:
                raw = (row.get("canonical_outcomes") or "").strip()
                canonical_names = [
                    part.strip() for part in raw.split("|") if part.strip()
                ]

                rows.append(
                    {
                        "bad_id": int(row["ID"]),
                        "bad_name": (row.get("Name") or "").strip(),
                        "canonical_names": canonical_names,
                    }
                )

        return rows

    def ensure_canonical_outcomes(self, canonical_names):
        lookup = {}
        created_count = 0

        for outcome in Outcome.objects.filter(name__in=canonical_names):
            lookup[outcome.name] = outcome

        for name in canonical_names:
            if name in lookup:
                continue

            outcome = Outcome.objects.create(name=name)
            lookup[name] = outcome
            created_count += 1
            self.stdout.write(f"Created canonical outcome: {name}")

        return lookup, created_count

    def apply_mapping(self, rows, canonical_lookup):
        summary = {
            "judgments_updated": 0,
            "judgment_links_added": 0,
            "judgment_links_removed": 0,
            "case_histories_updated": 0,
            "rows_skipped_unmapped": 0,
            "rows_skipped_missing_bad": 0,
            "rows_skipped_identity": 0,
        }

        bad_ids = [row["bad_id"] for row in rows]
        bad_outcomes = {
            outcome.id: outcome for outcome in Outcome.objects.filter(id__in=bad_ids)
        }

        for row in rows:
            bad_outcome = bad_outcomes.get(row["bad_id"])
            canonical_names = row["canonical_names"]

            if not bad_outcome:
                summary["rows_skipped_missing_bad"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping missing bad outcome id={row['bad_id']} "
                        f"name={row['bad_name']}"
                    )
                )
                continue

            if not canonical_names:
                summary["rows_skipped_unmapped"] += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping unmapped outcome id={bad_outcome.id} "
                        f"name={bad_outcome.name}"
                    )
                )
                continue

            canonical_outcomes = [canonical_lookup[name] for name in canonical_names]

            if (
                len(canonical_outcomes) == 1
                and canonical_outcomes[0].name == bad_outcome.name
            ):
                summary["rows_skipped_identity"] += 1
                self.stdout.write(
                    f"Skipping identity row: {bad_outcome.id} {bad_outcome.name}"
                )
                continue

            judgments = Judgment.objects.filter(outcomes=bad_outcome).distinct()
            judgment_count = judgments.count()

            case_history_qs = CaseHistory.objects.filter(outcome=bad_outcome)
            case_history_count = case_history_qs.count()

            self.stdout.write(
                f"{bad_outcome.id}: {bad_outcome.name} -> "
                f"{' | '.join(o.name for o in canonical_outcomes)} "
                f"(judgments={judgment_count}, case_histories={case_history_count})"
            )

            for judgment in judgments.iterator():
                judgment.outcomes.add(*canonical_outcomes)
                judgment.outcomes.remove(bad_outcome)
                summary["judgments_updated"] += 1
                summary["judgment_links_added"] += len(canonical_outcomes)
                summary["judgment_links_removed"] += 1

            if case_history_count:
                # CaseHistory is a single FK, so use the first canonical outcome.
                case_history_qs.update(outcome=canonical_outcomes[0])
                summary["case_histories_updated"] += case_history_count

        return summary
