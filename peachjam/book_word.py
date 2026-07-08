"""Convert Book markdown to/from DOCX for admin editing.

Books keep ``content_markdown`` as the source of truth. This module wraps Pandoc
for DOCX export/import and temporarily protects law-widget HTML so Word and
Pandoc treat those snippets as plain editor text during the round trip.
"""

import os
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from functools import lru_cache

DOCX_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
LAW_WIDGET_MARKER = "XX-la-akoma-ntoso"
LAW_WIDGET_TAG = "<la-akoma-ntoso"


class BookWordError(ValueError):
    """Raised when a DOCX import/export cannot be completed safely."""

    pass


@dataclass
class BookWordAnalysis:
    """Small set of import-preview metrics used by the Book admin."""

    character_count: int
    heading_count: int
    law_widget_count: int
    protected_law_widget_count: int
    image_count: int


def protect_law_widgets(markdown):
    """Replace law-widget opening tags with editor-safe text before DOCX export."""

    return (markdown or "").replace(LAW_WIDGET_TAG, LAW_WIDGET_MARKER)


def restore_law_widgets(markdown):
    """Restore protected law-widget lines and undo Pandoc escaping on those lines."""

    lines = []
    for line in (markdown or "").splitlines():
        if LAW_WIDGET_MARKER in line:
            line = line.replace(LAW_WIDGET_MARKER, LAW_WIDGET_TAG)
            line = line.replace("\\", "")
        lines.append(line)
    return "\n".join(lines)


def analyse_markdown(markdown):
    """Return simple stats and blockers for the import preview screen."""

    markdown = markdown or ""
    return BookWordAnalysis(
        character_count=len(markdown),
        heading_count=count_headings(markdown),
        law_widget_count=markdown.count(LAW_WIDGET_TAG),
        protected_law_widget_count=markdown.count(LAW_WIDGET_MARKER),
        image_count=count_image_references(markdown),
    )


def count_headings(markdown):
    """Count ATX and Setext Markdown headings."""

    markdown = markdown or ""
    atx_headings = re.findall(r"(?m)^#{1,6}\s+\S", markdown)
    setext_headings = re.findall(r"(?m)^.+\n(?:=+|-+)\s*$", markdown)
    return len(atx_headings) + len(setext_headings)


def count_image_references(markdown):
    """Count Markdown/HTML image references, which this importer deliberately blocks."""

    markdown = markdown or ""
    return len(re.findall(r"!\[[^\]]*\]\([^)]+\)|<img\b", markdown, flags=re.I))


def validate_docx(uploaded_file):
    """Reject unsupported or dirty DOCX files before passing them to Pandoc."""

    filename = os.path.basename(uploaded_file.name or "")
    if not filename.lower().endswith(".docx"):
        raise BookWordError("Only .docx files are supported.")

    try:
        uploaded_file.seek(0)
        with zipfile.ZipFile(uploaded_file) as docx:
            names = set(docx.namelist())
            if "word/document.xml" not in names:
                raise BookWordError("The uploaded file is not a valid DOCX document.")

            for name in names:
                if name.startswith("word/comments") and re.search(
                    rb"<w:comment(?:\s|>)", docx.read(name)
                ):
                    raise BookWordError(
                        "The uploaded DOCX contains comments. Remove comments and upload a clean DOCX."
                    )

            tracked_change_tags = (
                b"<w:ins",
                b"<w:del",
                b"<w:moveFrom",
                b"<w:moveTo",
                b"<w:cellIns",
                b"<w:cellDel",
                b"<w:cellMerge",
                b"<w:trackRevisions",
            )
            for name in names:
                if not name.startswith("word/") or not name.endswith(".xml"):
                    continue
                content = docx.read(name)
                if any(tag in content for tag in tracked_change_tags):
                    raise BookWordError(
                        "The uploaded DOCX contains tracked changes. Accept or reject changes and upload a clean DOCX."
                    )
    except zipfile.BadZipFile:
        raise BookWordError("The uploaded file is not a valid DOCX document.")
    finally:
        uploaded_file.seek(0)


def markdown_to_docx(markdown):
    """Render Book markdown to DOCX bytes, protecting law-widget snippets first."""

    with tempfile.NamedTemporaryFile(suffix=".md") as inf:
        with tempfile.NamedTemporaryFile(suffix=".docx") as outf:
            inf.write(protect_law_widgets(markdown).encode("utf-8"))
            inf.flush()
            _run_pandoc(
                [
                    "pandoc",
                    "--wrap=none",
                    "--from=markdown-smart",
                    "--to=docx",
                    "--output",
                    outf.name,
                    inf.name,
                ]
            )
            outf.seek(0)
            return outf.read()


def docx_to_markdown(uploaded_file):
    """Convert an uploaded clean DOCX to markdown and restore law-widget snippets."""

    validate_docx(uploaded_file)

    with tempfile.NamedTemporaryFile(suffix=".docx") as inf:
        with tempfile.NamedTemporaryFile(suffix=".md") as outf:
            for chunk in uploaded_file.chunks():
                inf.write(chunk)
            inf.flush()
            uploaded_file.seek(0)
            _run_pandoc(
                [
                    "pandoc",
                    "--wrap=none",
                    _markdown_headings_option(),
                    "--from=docx",
                    "--to=markdown-smart",
                    "--output",
                    outf.name,
                    inf.name,
                ]
            )
            outf.seek(0)
            return restore_law_widgets(outf.read().decode("utf-8"))


@lru_cache
def _markdown_headings_option():
    """Return the Pandoc option for ATX markdown headings across Pandoc versions."""

    try:
        help_text = subprocess.run(
            ["pandoc", "--help"], check=True, capture_output=True
        ).stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "--markdown-headings=atx"

    if "--markdown-headings" in help_text:
        return "--markdown-headings=atx"
    return "--atx-headers"


def _run_pandoc(cmd):
    """Run Pandoc and normalize process failures into ``BookWordError``."""

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        raise BookWordError("Pandoc is not installed or is not available on PATH.")
    except subprocess.CalledProcessError as e:
        message = e.stderr.decode("utf-8", errors="replace").strip()
        raise BookWordError(message or "Pandoc failed to convert the document.")
