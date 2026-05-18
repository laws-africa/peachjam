from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from peachjam.analysis.judges import (
    judge_identity_service,
)
from peachjam.models import Judge


class Command(BaseCommand):
    help = (
        "Backfill JudgePerson and JudgeAlias from legacy Judge records and relink "
        "Bench rows using canonical judge-name groups."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the clustering work without writing changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        judge_groups = defaultdict(list)

        legacy_judges = list(Judge.objects.order_by("pk"))
        if not legacy_judges:
            self.stdout.write(self.style.WARNING("No legacy judges found."))
            return

        for judge in legacy_judges:
            canonical_name = judge_identity_service.canonical_name_from_aliases(
                [judge.name]
            )
            judge_groups[
                judge_identity_service.normalize_judge_name(canonical_name)
            ].append(judge)

        merge_count = 0
        group_count = 0

        for normalized_name, judges in judge_groups.items():
            names = [judge.name for judge in judges]
            resolved = judge_identity_service.resolve_judge_person(
                names,
                dry_run=dry_run,
            )
            canonical_name = resolved["canonical_name"]
            aliases = resolved["aliases"]
            primary = resolved["judge_person"]
            duplicates = {
                alias.judge_person
                for alias in aliases
                if alias.judge_person_id and alias.judge_person_id != primary.pk
            }
            merge_count += len(duplicates)

            if dry_run:
                self.print_dry_run_group(canonical_name, judges)
                continue

            with transaction.atomic():
                alias_by_name = {alias.name: alias for alias in aliases}
                for judge in judges:
                    alias = alias_by_name.get(judge.name)
                    if alias is None:
                        alias, _ = judge_identity_service.assign_legacy_judge_to_person(
                            judge, primary
                        )
                        alias_by_name[judge.name] = alias
                    else:
                        updated_fields = []
                        if alias.judge_person_id != primary.pk:
                            alias.judge_person = primary
                            updated_fields.append("judge_person")
                        if (
                            alias.normalized_name
                            != judge_identity_service.normalize_judge_name(judge.name)
                        ):
                            updated_fields.append("normalized_name")
                        if updated_fields:
                            alias.save(update_fields=updated_fields)

                    if judge.description and not primary.description:
                        primary.description = judge.description
                        primary.save(update_fields=["description"])

                    judge_identity_service.assign_legacy_judge_to_person(
                        judge,
                        primary,
                        alias_name=alias.name,
                    )

                judge_identity_service.merge_judge_people(primary, list(duplicates))

            group_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete. Evaluated {len(judge_groups)} judge groups."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {group_count} judge groups and merged {merge_count} duplicates."
            )
        )

    def print_dry_run_group(self, canonical_name, judges):
        self.stdout.write(f"JudgePerson(full_name='{canonical_name}')")
        for judge in judges:
            parts = judge_identity_service.parse_judge_name(judge.name)
            title = parts["title"] or "-"
            self.stdout.write(
                "  JudgeAlias("
                f"name='{judge.name}', "
                f"normalized_name='{parts['normalized_name']}') "
                "-> Bench("
                f"judge='{judge.name}', "
                f"judge_person='{canonical_name}', "
                f"matched_alias='{judge.name}', "
                f"title='{title}')"
            )
