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

Parsing rules
-------------

Dashes (em-dash ``—``, en-dash ``–``, or spaced hyphen `` - ``) separate
levels::

    Criminal law — admissibility — trial within a trial
    → ['Criminal law', 'admissibility', 'trial within a trial']

Semicolons split sibling branches.  The tail portion of the current
path is replaced so that sibling or cousin branches share a common
prefix.

Examples::

    Criminal law — admissibility — trial within a trial;
    right to legal representation
    →  path 1: ['Criminal law', 'admissibility', 'trial within a trial']
       path 2: ['Criminal law', 'admissibility', 'right to legal representation']

    Criminal law — admissibility — trial within a trial;
    circumstantial evidence — Blom principles
    →  path 1: ['Criminal law', 'admissibility', 'trial within a trial']
       path 2: ['Criminal law', 'circumstantial evidence', 'Blom principles']

    Criminal law — admissibility — trial within a trial;
    self-defence plea
    →  path 1: ['Criminal law', 'admissibility', 'trial within a trial']
       path 2: ['Criminal law', 'admissibility', 'self-defence plea']
"""

import logging
import re

from django.db import IntegrityError, transaction
from django.utils.html import strip_tags
from django.utils.text import slugify

from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote

log = logging.getLogger(__name__)


class FlynoteParser:
    """Parses raw flynote text into structured paths.

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
        """Parse flynote text into a list of paths.

        See module docstring for full parsing rules.

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
    def update_for_judgment(self, judgment, refresh_counts=True):
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
                root = flynote.get_root()
                roots_to_refresh.add(root)
            for root in roots_to_refresh:
                FlynoteDocumentCount.refresh_for_flynote(root)
