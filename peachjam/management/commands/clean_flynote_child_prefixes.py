import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from peachjam.analysis.flynotes import FlynoteParser
from peachjam.models import Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote

LAW_SUFFIX_RE = re.compile(r"\s+law$", re.I)


def clean_spaces(value):
    return " ".join((value or "").split()).strip()


def prefix_variants(root_name):
    root_name = clean_spaces(root_name)
    variants = [root_name]

    short_name = LAW_SUFFIX_RE.sub("", root_name).strip()
    if short_name and short_name.casefold() != root_name.casefold():
        variants.append(short_name)

    return variants


def strip_redundant_prefix(root_name, child_name):
    child_name = clean_spaces(child_name)

    for prefix in prefix_variants(root_name):
        pattern = re.compile(
            rf"^{re.escape(prefix)}\s*/\s*(?P<rest>.+)$",
            re.I,
        )
        match = pattern.match(child_name)
        if match:
            return match.group("rest").strip(" /-")

    return None


class Command(BaseCommand):
    help = (
        "Remove redundant parent prefixes from direct child flynotes, for "
        "example 'Defamation/communications' under the 'Defamation' root."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Persist changes. Without this flag the command runs as a dry-run.",
        )

    def handle(self, *args, **options):
        dry_run = not options["apply"]
        if dry_run:
            self.stdout.write(
                "Running in dry-run mode. Re-run with --apply to persist changes."
            )

        total_roots_touched = 0
        total_renamed = 0
        total_merged = 0
        total_judgments_updated = 0

        roots = list(Flynote.get_root_nodes().order_by("name"))

        for root in roots:
            children = list(root.get_children().order_by("name", "pk"))

            candidate_by_pk = {}
            groups = defaultdict(list)

            for child in children:
                new_name = strip_redundant_prefix(root.name, child.name)
                if not new_name:
                    continue

                normalised = FlynoteParser.normalise_name(new_name)
                if not normalised:
                    continue

                row = {
                    "child": child,
                    "new_name": new_name,
                    "norm": normalised,
                }
                candidate_by_pk[child.pk] = row
                groups[normalised].append(row)

            if not groups:
                continue

            total_roots_touched += 1
            root_renamed = 0
            root_merged = 0
            affected_judgment_ids = set()

            self.stdout.write(f"ROOT {root.pk}: {root.name}")

            with transaction.atomic():
                for norm, rows in sorted(groups.items(), key=lambda item: item[0]):
                    existing_target = next(
                        (
                            sibling
                            for sibling in children
                            if sibling.pk not in candidate_by_pk
                            and FlynoteParser.normalise_name(sibling.name) == norm
                        ),
                        None,
                    )

                    rename_row = None
                    if existing_target:
                        target = existing_target
                        merge_rows = rows
                    else:
                        rename_row = rows[0]
                        target = rename_row["child"]
                        merge_rows = rows[1:]

                    if rename_row:
                        node = target
                        self.stdout.write(
                            f"RENAME  {node.pk}: {node.name!r} -> {rename_row['new_name']!r}"
                        )
                        if not dry_run:
                            affected_judgment_ids.update(
                                JudgmentFlynote.objects.filter(
                                    flynote__path__startswith=node.path
                                )
                                .values_list("document_id", flat=True)
                                .distinct()
                            )
                            node.name = rename_row["new_name"]
                            node.full_clean()
                            node.save(update_fields=["name"])
                        root_renamed += 1

                    for row in merge_rows:
                        source = row["child"]
                        self.stdout.write(
                            f"MERGE   {source.pk}: {source.name!r} -> {target.pk}"
                        )
                        if not dry_run:
                            affected_judgment_ids.update(
                                JudgmentFlynote.objects.filter(
                                    flynote__path__startswith=source.path
                                )
                                .values_list("document_id", flat=True)
                                .distinct()
                            )
                            target.merge_sources_into([source])
                        root_merged += 1

                if not dry_run and (root_renamed or root_merged):
                    for judgment in Judgment.objects.filter(
                        pk__in=affected_judgment_ids
                    ).only("pk"):
                        judgment.serialise_flynote_tree()
                        judgment.save(update_fields=["flynote", "flynote_raw"])

                    FlynoteDocumentCount.refresh_for_flynote(root)

            total_renamed += root_renamed
            total_merged += root_merged
            total_judgments_updated += len(affected_judgment_ids)

            self.stdout.write(
                "ROOT DONE: renamed={}, merged={}, judgments_updated={}".format(
                    root_renamed,
                    root_merged,
                    len(affected_judgment_ids),
                )
            )

        if not total_roots_touched:
            self.stdout.write("Nothing to clean.")

        self.stdout.write(
            "Done. roots_touched={}, renamed={}, merged={}, "
            "judgments_updated={}, dry_run={}".format(
                total_roots_touched,
                total_renamed,
                total_merged,
                total_judgments_updated,
                dry_run,
            )
        )
