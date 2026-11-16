#!/usr/bin/env python3
"""Compare exported Kenyan gazette timestamps without querying or changing either site."""

import argparse
import csv
import re
import sys
from datetime import datetime


def read_export(path):
    with open(path, newline="", encoding="utf-8") as source:
        return {
            row["expression_frbr_uri"]: datetime.fromisoformat(
                row["updated_at"].replace("Z", "+00:00")
            )
            for row in csv.DictReader(source)
            if re.fullmatch(
                r"/akn/ke(?:-[^/]+)?/officialGazette/.+", row["expression_frbr_uri"]
            )
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kenyalaw_export")
    parser.add_argument("gazettes_export")
    args = parser.parse_args()
    source = read_export(args.kenyalaw_export)
    destination = read_export(args.gazettes_export)
    writer = csv.writer(sys.stdout)
    writer.writerow(
        ["expression_frbr_uri", "reason", "source_updated_at", "destination_updated_at"]
    )
    for uri, timestamp in source.items():
        existing = destination.get(uri)
        if existing is None or timestamp != existing:
            writer.writerow(
                [
                    uri,
                    "missing" if existing is None else "timestamp_differs",
                    timestamp.isoformat(),
                    existing.isoformat() if existing else "",
                ]
            )


if __name__ == "__main__":
    main()
