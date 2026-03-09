#!/usr/bin/env python3
"""List help_link references used by PeachJam help buttons.

Usage:
    python scripts/list_help_links.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Python: context["help_link"] = "..." and {"help_link": "..."}
PY_HELP_LINK_VALUE_RE = re.compile(
    r"(?:context\[\s*['\"]help_link['\"]\s*\]\s*=\s*|['\"]help_link['\"]\s*:\s*)(['\"])(?P<value>.+?)\1"
)

# Templates: include with explicit help_link value.
TEMPLATE_INCLUDE_VALUE_RE = re.compile(
    r"include\s+[\"']peachjam/_help_button\.html[\"']\s+with\s+help_link\s*=\s*([\"'])(?P<value>.+?)\1"
)

# Templates: help button include expects help_link in context.
TEMPLATE_INCLUDE_CONTEXT_RE = re.compile(
    r"include\s+[\"']peachjam/_help_button\.html[\"']"
)

# Templates: direct help_link variable usage.
TEMPLATE_HELP_LINK_VAR_RE = re.compile(r"\bhelp_link\b")


def discover_scan_dirs() -> list[Path]:
    scan_dirs: set[Path] = set()
    for path in ROOT.iterdir():
        if not path.is_dir():
            continue
        if path.name.startswith("peachjam") or (path / "__init__.py").exists():
            scan_dirs.add(path)
    return sorted(scan_dirs)


def iter_files() -> list[Path]:
    files = []
    for base in discover_scan_dirs():
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix in {".py", ".html"}:
                files.append(path)
    return sorted(files)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def collect_rows() -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []

    for path in iter_files():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        lines = content.splitlines()

        for line_number, line in enumerate(lines, start=1):
            if path.suffix == ".py":
                for match in PY_HELP_LINK_VALUE_RE.finditer(line):
                    rows.append((relative(path), line_number, match.group("value")))
                continue

            # .html
            include_value_match = TEMPLATE_INCLUDE_VALUE_RE.search(line)
            if include_value_match:
                rows.append(
                    (relative(path), line_number, include_value_match.group("value"))
                )

    return rows


def main() -> int:
    rows = collect_rows()

    if not rows:
        print("No help_link references found.")
        return 0

    print("help_link references")
    print("====================")
    for path, line_number, value in rows:
        print(f"{path}:{line_number}\t{value}")

    unique_values = sorted({value for _, _, value in rows})

    print("\nunique help_link values")
    print("======================")
    for value in unique_values:
        print(value)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
