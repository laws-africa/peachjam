import re

from django.core.management.base import BaseCommand

from peachjam.models.flynote import Flynote

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

        cleaned_any = False
        roots = list(Flynote.get_root_nodes().order_by("name"))

        for root in roots:
            children = list(root.get_children().order_by("name", "pk"))
            pending = [
                (child, strip_redundant_prefix(root.name, child.name))
                for child in children
            ]
            pending = [(child, new_name) for child, new_name in pending if new_name]
            if not pending:
                continue

            cleaned_any = True
            root_renamed = 0
            root_merged = 0
            self.stdout.write(f"ROOT {root.pk}: {root.name}")
            if dry_run:
                for child, new_name in pending:
                    duplicate = (
                        child.get_siblings()
                        .exclude(pk=child.pk)
                        .filter(name__iexact=new_name)
                        .first()
                    )
                    if duplicate:
                        self.stdout.write(
                            f"MERGE   {child.pk}: {child.name!r} -> {duplicate.pk}"
                        )
                        root_merged += 1
                        continue

                    self.stdout.write(
                        f"RENAME  {child.pk}: {child.name!r} -> {new_name!r}"
                    )
                    root_renamed += 1
            else:
                for child, new_name in pending:
                    source_pk = child.pk
                    source_name = child.name
                    target, action = child.rename_to_or_merge(new_name)
                    if action == "merge":
                        self.stdout.write(
                            f"MERGE   {source_pk}: {source_name!r} -> {target.pk}"
                        )
                        root_merged += 1
                    else:
                        self.stdout.write(
                            f"RENAME  {source_pk}: {source_name!r} -> {new_name!r}"
                        )
                        root_renamed += 1

            self.stdout.write(
                "ROOT DONE: renamed={}, merged={}".format(root_renamed, root_merged)
            )

        if not cleaned_any:
            self.stdout.write("Nothing to clean.")
            return

        self.stdout.write("Done.")
