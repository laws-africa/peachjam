import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from peachjam.analysis.flynotes import FlynoteParser
from peachjam.models import Judgment


def clean_xlsx_value(value):
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub("", value)
    return value


class Command(BaseCommand):
    help = "Run the flynote parser over judgments and export a CSV report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help="Path to the CSV or XLSX file to write.",
        )
        parser.add_argument(
            "--csv-output",
            help="Optional path to write a CSV report.",
        )
        parser.add_argument(
            "--xlsx-output",
            help="Optional path to write an Excel report.",
        )
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
            help="Analyze a single judgment by primary key.",
        )
        parser.add_argument(
            "--start-id",
            type=int,
            default=None,
            help="Start processing from this judgment PK downwards.",
        )

    def handle(self, *args, **options):
        parser = FlynoteParser()
        csv_output = options["csv_output"]
        xlsx_output = options["xlsx_output"]
        if options["output"]:
            if options["output"].lower().endswith(".xlsx"):
                xlsx_output = xlsx_output or options["output"]
            else:
                csv_output = csv_output or options["output"]

        if not csv_output and not xlsx_output:
            xlsx_output = str(Path.cwd() / "flynotes_analysis.xlsx")

        if options["judgment_id"]:
            qs = Judgment.objects.non_polymorphic().filter(pk=options["judgment_id"])
        else:
            qs = (
                Judgment.objects.non_polymorphic()
                .exclude(flynote__isnull=True)
                .exclude(flynote="")
                .order_by("-pk")
            )

            if options["start_id"]:
                qs = qs.filter(pk__lte=options["start_id"])

            if options["limit"]:
                qs = qs[: options["limit"]]

        fieldnames = [
            "pk",
            "expression_frbr_uri",
            "case_name",
            "raw_flynote",
            "normalised_flynote",
            "flynote_depth",
            "flynote_1",
            "flynote_2",
            "flynote_3",
            "flynote_4",
            "flynote_5",
            "flynote_6_plus",
            "flynote_line_count",
            "parsed_path_count",
            "max_depth",
            "has_depth_gt_5",
            "paths_json",
        ]

        rows = []
        for judgment in qs.iterator():
            normalised = parser.normalise_multiline_text(judgment.flynote)
            paths = parser.parse(judgment.flynote)
            deepest_path = max(paths, key=len, default=[])
            max_depth = len(deepest_path)
            rows.append(
                {
                    "pk": judgment.pk,
                    "expression_frbr_uri": judgment.expression_frbr_uri,
                    "case_name": judgment.case_name,
                    "raw_flynote": judgment.flynote,
                    "normalised_flynote": normalised,
                    "flynote_depth": max_depth,
                    "flynote_1": deepest_path[0] if len(deepest_path) > 0 else "",
                    "flynote_2": deepest_path[1] if len(deepest_path) > 1 else "",
                    "flynote_3": deepest_path[2] if len(deepest_path) > 2 else "",
                    "flynote_4": deepest_path[3] if len(deepest_path) > 3 else "",
                    "flynote_5": deepest_path[4] if len(deepest_path) > 4 else "",
                    "flynote_6_plus": " | ".join(deepest_path[5:]),
                    "flynote_line_count": len(
                        [line for line in normalised.splitlines() if line.strip()]
                    ),
                    "parsed_path_count": len(paths),
                    "max_depth": max_depth,
                    "has_depth_gt_5": max_depth > 5,
                    "paths_json": json.dumps(paths, ensure_ascii=False),
                }
            )

        if csv_output:
            with open(csv_output, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        if xlsx_output:
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "flynotes"
            sheet.append(fieldnames)
            for row in rows:
                sheet.append([clean_xlsx_value(row[field]) for field in fieldnames])
            workbook.save(xlsx_output)

        outputs = ", ".join(path for path in [csv_output, xlsx_output] if path)
        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote parser report for {len(rows)} judgments to {outputs}"
            )
        )
