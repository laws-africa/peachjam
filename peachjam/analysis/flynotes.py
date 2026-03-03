"""Flynote text parsing.

Judgments in Southern/East African legal databases carry a short structured
summary called a *flynote*.  Flynotes use dashes to express hierarchy and
semicolons to separate sibling branches::

    Criminal law — admissibility — trial within a trial;
    right to legal representation

This module converts that notation into taxonomy paths.

One class is exposed:

* **FlynoteParser** – stateless text-to-paths converter with HTML cleaning.
"""

import re

from django.utils.html import strip_tags
from django.utils.text import slugify


class FlynoteParser:
    """Parses raw flynote text into structured taxonomy paths.

    Handles HTML stripping, dash/semicolon splitting, and hierarchical
    path construction from legal flynote conventions.

    Usage::

        parser = FlynoteParser()
        paths = parser.parse(
            "Criminal law — admissibility — trial within a trial"
        )
        # paths == [['Criminal law', 'admissibility', 'trial within a trial']]
    """

    DASH_PATTERN = r"\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+"
    MAX_NAME_LENGTH = 255

    @staticmethod
    def clean(text):
        """Clean HTML tags and normalise whitespace in a flynote.

        Strips HTML tags and entities, collapses whitespace, removes leading
        bullet characters, and strips trailing periods.
        """
        if not text:
            return ""

        text = strip_tags(text).strip()
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^[\-\u2022\u2023\u25E6\u2043\s]+", "", text)
        text = text.strip().rstrip(".")
        return text

    def parse(self, text):
        """Parse flynote text into a list of taxonomy paths.

        The parsing works as follows:

        1. HTML tags and entities are stripped, whitespace is normalised,
           and trailing periods are removed (via ``clean``).
        2. If no dash characters (em-dash, en-dash, or spaced hyphen) are
           found, the text is treated as plain prose and an empty list is
           returned.
        3. The text is split on semicolons into segments.
        4. Each segment is split on dashes into parts, forming a hierarchy
           from general to specific.
        5. For the first segment, the parts become the initial path.
        6. For each subsequent segment, the number of dash-separated parts
           (n) determines how many levels from the bottom of the current
           path are replaced.  This allows sibling or cousin branches to
           share a common prefix.

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
            text: Raw flynote string, potentially containing HTML markup.

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

        segments = [s.strip() for s in text.split(";") if s.strip()]

        current_path = []
        paths = []

        for segment in segments:
            parts = [
                p.strip()[: self.MAX_NAME_LENGTH]
                for p in re.split(self.DASH_PATTERN, segment)
                if p.strip()
            ]
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
    def normalise_name(name):
        """Convert a topic name to a slug for deduplication matching.

        Examples::

            >>> FlynoteParser.normalise_name("Criminal Law")
            'criminal-law'
            >>> FlynoteParser.normalise_name("  Right to fair hearing  ")
            'right-to-fair-hearing'
        """
        return slugify(name)
