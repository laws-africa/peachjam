"""Flynote text parsing and Flynote model synchronisation.

Judgments in Southern/East African legal databases carry a short structured
summary called a *flynote*.  Flynotes use dashes to express hierarchy and
semicolons to separate sibling branches::

    Criminal law — admissibility — trial within a trial;
    right to legal representation

This module converts that notation into paths and keeps the
Django ``Flynote`` / ``JudgmentFlynote`` tables in sync with each judgment's
flynote field.

Two classes are exposed:

* **FlynoteParser** – stateless text-to-paths converter.
* **FlynoteUpdater** – creates/reuses ``Flynote`` nodes and links
  them to a ``Judgment`` via ``JudgmentFlynote``.
"""

import logging
import re

from django.db import IntegrityError, transaction
from django.utils.text import slugify

from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote

log = logging.getLogger(__name__)


class FlynoteParser:
    """Parses raw flynote text into structured paths.

    Handles dash/semicolon splitting and hierarchical path construction from
    legal flynote conventions.

    Usage::

        parser = FlynoteParser()
        paths = parser.parse(
            "Criminal law — admissibility — trial within a trial"
        )
        # paths == [['Criminal law', 'admissibility', 'trial within a trial']]
    """

    DASH_PATTERN = r"\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+"
    MAX_NAME_LENGTH = 255
    HELD_PATTERN = re.compile(r"\bHeld:\s*", re.IGNORECASE)
    SENTENCE_BOUNDARY_PATTERN = re.compile(r"(?<=\.)\s+(?=[A-Z])")
    REPORT_MARKER_PATTERN = re.compile(
        r"^(?:[A-Z])\s+(?=[A-Z][^-–—]{1,80}(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+))"
    )
    TOPIC_RESTART_PATTERN = re.compile(
        r"(?P<phrase>[A-Z][A-Za-z/&'()]+(?:\s+[A-Za-z][A-Za-z/&'()]+){0,6})"
        r"(?:\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+)"
    )
    REFERENCE_TAIL_PATTERN = re.compile(
        r"^(?:"
        r"[A-Z][A-Za-z'()]+(?:\s+[A-Z][A-Za-z'()]+){0,8}\s+"
        r"(?:Act|Ordinance|Rules?|Code|Regulations?|Agreement)"
        r"(?:,?\s+\d{4})?"
        r"|[A-Z][A-Za-z'()]+(?:\s+[A-Z][A-Za-z'()]+){0,8}\s+Order in Council"
        r"|(?:Section|Sections|Order|Rule|Rules|Cap\.)\s*[\dIVXLCM]"
        r"|s\.\s*\d"
        r"|O\.\s*\d"
        r"|r\.\s*\d"
        r")",
        re.IGNORECASE,
    )

    @staticmethod
    def clean(text):
        """Normalise whitespace in a flynote.

        Preserves line breaks so multi-line flynotes can be interpreted as one
        flynote per line. Within each line, whitespace is normalised, leading
        bullet characters are removed, and trailing periods are stripped.
        """
        if not text:
            return ""

        lines = []
        for line in text.strip().splitlines():
            line = re.sub(r"\s+", " ", line)
            line = re.sub(r"^[\-\u2022\u2023\u25E6\u2043\s]+", "", line)
            line = line.strip().rstrip(".")
            if line:
                lines.append(line)
        return "\n".join(lines)

    def normalise_multiline_text(self, text):
        """Normalise flynote text into one flynote per line."""
        text = self.clean(text)
        if not text:
            return ""

        text = self._strip_held_section(text)
        candidates = []
        for line in text.splitlines():
            candidates.extend(self._split_line_into_candidates(line))

        return "\n".join(self._dedupe_candidates(candidates))

    def parse(self, text):
        """Parse flynote text into a list of paths.

        The parsing works as follows:

        1. Whitespace is normalised and trailing periods are removed
           (via ``clean``).
        2. If no dash characters (em-dash, en-dash, or spaced hyphen) are
           found, the text is treated as plain prose and an empty list is
           returned.
        3. The text is split into lines and each line is treated as a separate
           flynote.
        4. Within each flynote, the text is split on semicolons into segments.
        5. Each segment is split on dashes into parts, forming a hierarchy
           from general to specific.
        6. For the first segment in a flynote, the parts become the initial
           path.
        7. For each subsequent segment in that flynote, the number of
           dash-separated parts (n) determines how many levels from the bottom
           of the current path are replaced. This allows sibling or cousin
           branches to share a common prefix.

        Examples::

            >>> parser = FlynoteParser()

            # Single chain – three levels deep
            >>> parser.parse("Criminal law — admissibility — trial within a trial")
            [['Criminal law', 'admissibility', 'trial within a trial']]

            # Semicolons create sibling branches (1 part replaces the last level)
            >>> parser.parse(
            ...     "Criminal law — admissibility — trial within a trial; "
            ...     "right to representation"
            ... )
            [['Criminal law', 'admissibility', 'trial within a trial'],
             ['Criminal law', 'admissibility', 'right to representation']]

            # Two dash-separated parts replace the last two levels
            >>> parser.parse(
            ...     "Criminal law — admissibility — trial; "
            ...     "circumstantial evidence — Blom principles"
            ... )
            [['Criminal law', 'admissibility', 'trial'],
             ['Criminal law', 'circumstantial evidence', 'Blom principles']]

            # Plain prose (no dashes) returns an empty list
            >>> parser.parse("Contract between a lender and a borrower.")
            []

        Args:
            text: Raw flynote string.

        Returns:
            A list of paths, where each path is a list of strings from
            root to leaf.  Returns an empty list if the text is empty,
            has no dashes, or is plain prose.
        """
        text = self.clean(text)

        if not text:
            return []

        if not re.search(self.DASH_PATTERN, text):
            return []

        paths = []
        for line in self.normalise_multiline_text(text).splitlines():
            segments = [s.strip() for s in self._split_segments(line) if s.strip()]
            current_path = []

            for segment in segments:
                parts = [
                    p.strip()[: self.MAX_NAME_LENGTH]
                    for p in self._split_dash_parts(segment)
                    if p.strip()
                ]
                parts = self._trim_reference_tail(parts)
                if not parts:
                    continue

                n = len(parts)
                if not current_path:
                    current_path = parts
                else:
                    current_path = current_path[: max(len(current_path) - n, 0)] + parts

                paths.append(list(current_path))

        return paths

    @staticmethod
    def _split_segments(text):
        segments = []
        current = []
        depth = 0
        for ch in text:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth = max(depth - 1, 0)
                current.append(ch)
            elif ch == ";" and depth == 0:
                segments.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            segments.append("".join(current))
        return segments

    def _split_dash_parts(self, text):
        """Split a hierarchy segment on dashes, ignoring dashes inside parentheses."""
        parts = []
        current = []
        depth = 0
        i = 0

        while i < len(text):
            ch = text[i]
            if ch == "(":
                depth += 1
                current.append(ch)
                i += 1
                continue
            if ch == ")":
                depth = max(depth - 1, 0)
                current.append(ch)
                i += 1
                continue

            if depth == 0:
                match = re.match(self.DASH_PATTERN, text[i:])
                if match:
                    parts.append("".join(current))
                    current = []
                    i += match.end()
                    continue

            current.append(ch)
            i += 1

        if current:
            parts.append("".join(current))

        return parts

    def _strip_held_section(self, text):
        return self.HELD_PATTERN.split(text, maxsplit=1)[0].strip()

    def _split_line_into_candidates(self, line):
        if not line:
            return []

        parts = self.SENTENCE_BOUNDARY_PATTERN.split(line)
        candidates = []
        current = ""

        for part in parts:
            part = self._clean_candidate(part)
            if not part:
                continue

            if current and self._starts_new_flynote(part):
                candidates.append(current)
                current = part
            else:
                current = f"{current}. {part}" if current else part

        if current:
            candidates.append(current)

        split_candidates = []
        for candidate in candidates:
            split_candidates.extend(self._split_topic_restarts(candidate))

        return split_candidates

    def _starts_new_flynote(self, text):
        head = text[:120]
        if not re.search(self.DASH_PATTERN, head):
            return False

        parts = [p.strip() for p in self._split_dash_parts(text) if p.strip()]
        if len(parts) < 2:
            return False

        return self._looks_like_heading_phrase(parts[0], allow_single_word=True)

    def _clean_candidate(self, text):
        text = text.strip().rstrip(".;,")
        text = self.REPORT_MARKER_PATTERN.sub("", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _split_topic_restarts(self, text):
        boundaries = []
        for match in self.TOPIC_RESTART_PATTERN.finditer(text):
            if match.start() == 0:
                continue

            if re.search(self.DASH_PATTERN + r"$", text[: match.start()]):
                continue

            if not self._looks_like_topic_restart(text, match):
                continue

            boundaries.append(match.start())

        if not boundaries:
            return [text]

        parts = []
        start = 0
        for boundary in boundaries:
            part = text[start:boundary].strip()
            if part:
                parts.append(part)
            start = boundary

        tail = text[start:].strip()
        if tail:
            parts.append(tail)

        return parts

    def _looks_like_topic_restart(self, text, match):
        phrase = match.group("phrase").strip()
        if not self._looks_like_heading_phrase(phrase, allow_single_word=False):
            return False

        tail = text[match.start() :].strip()
        if len([p for p in self._split_dash_parts(tail) if p.strip()]) < 2:
            return False

        return True

    @staticmethod
    def _looks_like_heading_phrase(phrase, allow_single_word):
        words = re.findall(r"[A-Za-z][A-Za-z/&'()]+", phrase)
        if not 1 <= len(words) <= 8:
            return False

        phrase_lc = phrase.casefold()
        if phrase_lc.startswith(
            (
                "whether ",
                "when ",
                "where ",
                "if ",
                "right to ",
                "duty to ",
                "failure to ",
                "requirement of ",
                "application for ",
                "submission on ",
                "scope of ",
                "independence of ",
                "recognition of ",
                "conclusion:",
            )
        ):
            return False

        connector_words = {
            "and",
            "of",
            "the",
            "in",
            "on",
            "for",
            "to",
            "at",
            "by",
            "under",
            "with",
            "or",
            "v",
        }

        has_title_word = False
        title_word_count = 0
        for word in words:
            if word.islower():
                if word.casefold() not in connector_words:
                    return False
                continue

            if word[0].isupper():
                has_title_word = True
                title_word_count += 1
                continue

            return False

        if not has_title_word:
            return False

        if not allow_single_word and title_word_count < 2:
            return False

        return True

    def _trim_reference_tail(self, parts):
        trimmed = []
        for idx, part in enumerate(parts):
            if idx >= 2 and self._looks_like_reference_tail(part):
                break
            trimmed.append(part)
        return trimmed

    def _looks_like_reference_tail(self, part):
        text = part.strip()
        if not text:
            return False

        if not self.REFERENCE_TAIL_PATTERN.search(text):
            return False

        # Don't drop substantive issue statements that merely cite a section.
        if text.lower().startswith(
            (
                "whether ",
                "when ",
                "if ",
                "where ",
                "duty ",
                "right ",
                "application under ",
            )
        ):
            return False

        return True

    def _dedupe_candidates(self, candidates):
        seen = set()
        deduped = []

        for candidate in candidates:
            candidate = self._clean_candidate(candidate)
            if not candidate:
                continue

            canonical = self._canonicalise_candidate(candidate)
            if canonical in seen:
                continue

            seen.add(canonical)
            deduped.append(candidate)

        return deduped

    @staticmethod
    def _canonicalise_candidate(text):
        text = text.casefold()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s*[\u2014\u2013-]\s*", " - ", text)
        return text.strip(" .;,")

    @staticmethod
    def normalise_name(name):
        """Convert a topic name to a slug for deduplication matching."""
        return slugify(name)


class FlynoteUpdater:
    """Manages the Flynote tree for flynote-derived topics.

    Builds (or reuses) ``Flynote`` nodes for each path segment, and creates
    ``JudgmentFlynote`` links so that the judgment appears under the correct
    leaf topics. Uses treebeard's MP_Node for tree management.

    Usage::

        updater = FlynoteUpdater()
        updater.update_for_judgment(judgment)
    """

    def __init__(self):
        self.parser = FlynoteParser()

    def get_or_create_node(self, parent, name):
        """Find an existing Flynote whose slug matches, or create a new one.

        *parent* is the parent Flynote node, or None for top-level.

        Returns ``None`` if the name produces an empty slug.
        """
        normalised = FlynoteParser.normalise_name(name)
        if not normalised:
            return None

        if parent:
            expected_slug = f"{parent.slug}-{normalised}"
        else:
            expected_slug = normalised

        existing = Flynote.objects.filter(slug=expected_slug).first()
        if existing:
            return existing

        try:
            if parent:
                node = parent.add_child(name=name, slug=expected_slug)
            else:
                node = Flynote.add_root(name=name, slug=expected_slug)
            return node
        except IntegrityError:
            return Flynote.objects.filter(slug=expected_slug).first()

    @transaction.atomic
    def update_for_judgment(self, judgment, refresh_counts=False):
        """Parse a judgment's flynote and sync its Flynote links.

        1. Deletes all existing ``JudgmentFlynote`` links for this judgment.
        2. Parses ``judgment.flynote`` into hierarchical paths.
        3. For each path, walks (or creates) ``Flynote`` nodes from root to leaf.
        4. Links the judgment to the leaf node of every path.

        Does nothing if the flynote text cannot be parsed (plain prose, empty, etc.).
        """
        JudgmentFlynote.objects.filter(document=judgment).delete()

        paths = self.parser.parse(judgment.flynote)
        if not paths:
            return

        leaf_flynotes = set()
        for path in paths:
            parent = None
            for name in path:
                node = self.get_or_create_node(parent, name)
                if node is None:
                    break
                parent = node
            else:
                leaf_flynotes.add(node)

        for flynote in leaf_flynotes:
            JudgmentFlynote.objects.get_or_create(document=judgment, flynote=flynote)

        log.info(
            "Linked judgment %s to %s flynote topics.",
            judgment.pk,
            len(leaf_flynotes),
        )

        if refresh_counts and leaf_flynotes:
            roots_to_refresh = set()
            for flynote in leaf_flynotes:
                roots_to_refresh.add(flynote.get_root())
            for root in roots_to_refresh:
                FlynoteDocumentCount.refresh_for_flynote(root)
