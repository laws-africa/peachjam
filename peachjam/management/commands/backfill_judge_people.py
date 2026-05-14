from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from peachjam.analysis.judges import (
    canonical_name_from_aliases,
    merge_judges,
    normalize_judge_name,
    parse_judge_name,
    unique_judge_slug,
)
from peachjam.models import Bench, Judge, JudgeAlias, JudgePerson


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
            canonical_name = canonical_name_from_aliases([judge.name])
            judge_groups[normalize_judge_name(canonical_name)].append(judge)

        merge_count = 0
        group_count = 0

        for normalized_name, judges in judge_groups.items():
            names = [judge.name for judge in judges]
            canonical_name = canonical_name_from_aliases(names)
            alias_normalized_names = {
                normalize_judge_name(judge.name) for judge in judges
            }
            aliases = list(
                JudgeAlias.objects.filter(normalized_name__in=alias_normalized_names)
                .select_related("judge_person")
                .order_by("-is_verified", "pk")
            )
            primary = self.get_or_create_primary(
                aliases=aliases,
                canonical_name=canonical_name,
                dry_run=dry_run,
            )
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
                        alias = JudgeAlias.objects.create(
                            judge_person=primary,
                            name=judge.name,
                            normalized_name=normalize_judge_name(judge.name),
                            description=judge.description,
                            is_verified=True,
                        )
                        alias_by_name[judge.name] = alias
                    else:
                        updated_fields = []
                        if alias.judge_person_id != primary.pk:
                            alias.judge_person = primary
                            updated_fields.append("judge_person")
                        judge_normalized_name = normalize_judge_name(judge.name)
                        if alias.normalized_name != judge_normalized_name:
                            alias.normalized_name = judge_normalized_name
                            updated_fields.append("normalized_name")
                        if not alias.description and judge.description:
                            alias.description = judge.description
                            updated_fields.append("description")
                        if updated_fields:
                            alias.save(update_fields=updated_fields)

                    self.update_bench_rows(
                        judge=judge, judge_person=primary, alias=alias
                    )

                merge_judges(primary, list(duplicates))

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

    def get_or_create_primary(self, aliases, canonical_name, dry_run):
        for alias in aliases:
            if (
                alias.judge_person_id
                and alias.judge_person.full_name.casefold() == canonical_name.casefold()
            ):
                return alias.judge_person

        existing_person = (
            JudgePerson.objects.filter(full_name__iexact=canonical_name)
            .order_by("pk")
            .first()
        )
        if existing_person:
            return existing_person

        if aliases and aliases[0].judge_person_id and not dry_run:
            aliases[0].judge_person.full_name = canonical_name
            aliases[0].judge_person.slug = unique_judge_slug(
                JudgePerson,
                canonical_name,
                pk=aliases[0].judge_person.pk,
            )
            aliases[0].judge_person.save(update_fields=["full_name", "slug"])
            return aliases[0].judge_person

        if dry_run:
            return (
                aliases[0].judge_person
                if aliases
                else JudgePerson(
                    full_name=canonical_name,
                    slug=canonical_name,
                )
            )

        return JudgePerson.objects.create(
            full_name=canonical_name,
            slug=unique_judge_slug(JudgePerson, canonical_name),
        )

    def update_bench_rows(self, judge, judge_person, alias):
        parts = parse_judge_name(judge.name)

        Bench.objects.filter(
            judge=judge,
            is_manual_override=False,
        ).update(
            judge_person=judge_person,
            matched_alias=alias,
            extracted_name=judge.name,
            title=parts["title"],
        )
        Bench.objects.filter(
            judge=judge,
            is_manual_override=True,
            judge_person__isnull=True,
        ).update(judge_person=judge_person)
        Bench.objects.filter(
            judge=judge,
            is_manual_override=True,
            matched_alias__isnull=True,
        ).update(matched_alias=alias)
        Bench.objects.filter(
            judge=judge,
            is_manual_override=True,
            extracted_name="",
        ).update(extracted_name=judge.name)
        Bench.objects.filter(
            judge=judge,
            is_manual_override=True,
            title="",
        ).update(title=parts["title"])

    def print_dry_run_group(self, canonical_name, judges):
        self.stdout.write(f"JudgePerson(full_name='{canonical_name}')")
        for judge in judges:
            parts = parse_judge_name(judge.name)
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
