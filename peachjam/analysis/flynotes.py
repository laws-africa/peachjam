"""Flynote text parsing and taxonomy synchronisation.

Judgments in Southern/East African legal databases carry a short structured
summary called a *flynote*.  Flynotes use dashes to express hierarchy and
semicolons to separate sibling branches::

    Criminal law — admissibility — trial within a trial;
    right to legal representation

This module converts that notation into taxonomy paths and keeps the
Django ``Taxonomy`` / ``DocumentTopic`` tables in sync with each judgment's
flynote field.

Two classes are exposed:

* **FlynoteParser** – stateless text-to-paths converter.
* **FlynoteTaxonomyUpdater** – creates/reuses ``Taxonomy`` nodes and links
  them to a ``Judgment`` via ``DocumentTopic``.
"""

import logging
import re

from django.db import IntegrityError, transaction
from django.utils.html import strip_tags
from django.utils.text import slugify

from peachjam.models.settings import pj_settings
from peachjam.models.taxonomies import DocumentTopic, Taxonomy

log = logging.getLogger(__name__)


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

    def parse(self, text):
        """Parse flynote text into a list of taxonomy paths.

        The parsing works as follows:

        1. HTML tags and entities are stripped, whitespace is normalised,
           and trailing periods are removed.
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
        if not text:
            return []

        text = strip_tags(text).strip()
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^[\-\u2022\u2023\u25E6\u2043\s]+", "", text)
        text = text.strip().rstrip(".")

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


class FlynoteTaxonomyUpdater:
    """Manages the taxonomy tree for flynote-derived topics.

    Reads the configured ``flynote_taxonomy_root`` from
    ``PeachJamSettings``, builds (or reuses) ``Taxonomy`` nodes for each
    path segment, and creates ``DocumentTopic`` links so that the judgment
    appears under the correct leaf topics.

    Usage::

        updater = FlynoteTaxonomyUpdater()
        updater.update_for_judgment(judgment)
    """

    def __init__(self):
        self.parser = FlynoteParser()

    def get_or_create_node(self, parent, name):
        """Find an existing child of *parent* whose normalised name matches,
        or create a new child node.

        Matching is case- and whitespace-insensitive (via
        ``FlynoteParser.normalise_name``), so "Criminal Law" will match an
        existing "Criminal law" node rather than creating a duplicate.

        If the slug already exists in the database (collision from a
        different tree path producing the same slug), the existing node
        is returned instead of raising an error.

        Returns ``None`` if the name produces an empty slug (e.g.
        punctuation-only strings).
        """
        normalised = FlynoteParser.normalise_name(name)
        if not normalised:
            return None

        children = parent.get_children() if parent else Taxonomy.get_root_nodes()
        for child in children:
            if FlynoteParser.normalise_name(child.name) == normalised:
                return child

        expected_slug = f"{parent.slug}-{normalised}" if parent else normalised
        existing = Taxonomy.objects.filter(slug=expected_slug).first()
        if existing:
            return existing

        try:
            if parent:
                return parent.add_child(name=name)
            else:
                return Taxonomy.add_root(name=name)
        except IntegrityError:
            return Taxonomy.objects.filter(slug=expected_slug).first()

    @transaction.atomic
    def update_for_judgment(self, judgment):
        """Parse a judgment's flynote and sync its taxonomy links.

        1. Deletes all existing ``DocumentTopic`` links between the judgment
           and any descendant of the flynote taxonomy root.
        2. Parses ``judgment.flynote`` into hierarchical paths.
        3. For each path, walks (or creates) ``Taxonomy`` nodes from root
           to leaf.
        4. Links the judgment to the leaf node of every path.

        Runs inside a database transaction so that a failure for one
        judgment does not leave the taxonomy tree in a corrupt state.

        Does nothing if no ``flynote_taxonomy_root`` is configured or if
        the flynote text cannot be parsed (plain prose, empty, etc.).
        """
        settings = pj_settings()
        root = settings.flynote_taxonomy_root
        if not root:
            log.warning("No flynote taxonomy root configured, skipping.")
            return

        flynote_descendant_ids = set(
            root.get_descendants().values_list("pk", flat=True)
        )
        DocumentTopic.objects.filter(
            document=judgment, topic_id__in=flynote_descendant_ids
        ).delete()

        paths = self.parser.parse(judgment.flynote)
        if not paths:
            return

        leaf_topics = set()
        for path in paths:
            current_parent = root
            for name in path:
                node = self.get_or_create_node(current_parent, name)
                if node is None:
                    break
                current_parent = node
            else:
                leaf_topics.add(current_parent)

        for topic in leaf_topics:
            DocumentTopic.objects.get_or_create(document=judgment, topic=topic)

        log.info(
            f"Linked judgment {judgment.pk} to "
            f"{len(leaf_topics)} flynote taxonomy topics."
        )
