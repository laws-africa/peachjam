import csv
import io
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase


class GazetteExportComparisonTest(SimpleTestCase):
    def test_comparison_includes_both_timestamp_directions_for_kenyan_gazettes(self):
        base = "/akn/ke/officialGazette/2026-11-13/"
        source = [
            (base + "missing/eng@2026-11-13", "2026-11-13T10:00:00Z"),
            (base + "newer/eng@2026-11-13", "2026-11-13T10:00:00Z"),
            (base + "same/eng@2026-11-13", "2026-11-13T10:00:00Z"),
            (base + "older/eng@2026-11-13", "2026-11-13T10:00:00Z"),
            (
                "/akn/ke-47/officialGazette/2026-11-13/1/eng@2026-11-13",
                "2026-11-13T10:00:00Z",
            ),
            (
                "/akn/za/officialGazette/2026-11-13/1/eng@2026-11-13",
                "2026-11-13T10:00:00Z",
            ),
            ("/akn/ke/act/2026/1/eng@2026-11-13", "2026-11-13T10:00:00Z"),
        ]
        destination = [
            (base + "newer/eng@2026-11-13", "2026-11-12T10:00:00Z"),
            (base + "same/eng@2026-11-13", "2026-11-13T13:00:00+03:00"),
            (base + "older/eng@2026-11-13", "2026-11-14T10:00:00Z"),
        ]
        with TemporaryDirectory() as directory:
            files = [
                Path(directory) / name for name in ("kenyalaw.csv", "gazettes.csv")
            ]
            for path, rows in zip(files, [source, destination]):
                with path.open("w", newline="") as output:
                    writer = csv.writer(output)
                    writer.writerow(["expression_frbr_uri", "updated_at"])
                    writer.writerows(rows)
            originals = [path.read_bytes() for path in files]
            result = subprocess.run(
                [
                    sys.executable,
                    str(
                        Path(__file__).resolve().parents[2]
                        / "scripts/compare-kenya-gazettes.py"
                    ),
                    *map(str, files),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual([path.read_bytes() for path in files], originals)
        rows = list(csv.DictReader(io.StringIO(result.stdout)))
        self.assertEqual(
            [(row["expression_frbr_uri"], row["reason"]) for row in rows],
            [
                (source[0][0], "missing"),
                (source[1][0], "timestamp_differs"),
                (source[3][0], "timestamp_differs"),
                (source[4][0], "missing"),
            ],
        )
