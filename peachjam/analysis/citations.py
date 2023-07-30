import logging
from bisect import bisect_left

import lxml.html
import requests
from django.conf import settings
from docpipe.matchers import ExtractedCitation

from peachjam.models import CitationLink

log = logging.getLogger(__name__)


class CitationAnalyser:
    matchers = []

    def extract_citations(self, document):
        """Run matchers across the HTML or text in this document."""
        if document.content_html_is_akn:
            # don't markup AKN HTML
            return False

        if document.content_html:
            # markup html
            return self.extract_citations_from_html(document)
        else:
            # markup the source file by extracting the text and assuming we'll render it as a PDF
            return self.extract_citations_from_source_file(document)

    def extract_citations_from_html(self, document):
        html = lxml.html.fromstring(document.content_html)
        for matcher in self.matchers:
            # the matcher can either manipulate the html, or return a new tree
            res = matcher().markup_html_matches(document.expression_uri(), html)
            html = html if res is None else res
        document.content_html = lxml.html.tostring(html, encoding="unicode")
        return True

    def extract_citations_from_source_file(self, document):
        text = document.get_content_as_text()
        if text:
            for matcher in self.matchers:
                matcher = matcher()
                matcher.extract_text_matches(document.expression_uri(), text)
                # get the indexes of all newlines in text, by page
                newlines = [
                    [i for i, c in enumerate(page) if c == "\n"]
                    for page in text.split("\x0C")
                ]
                self.store_text_citation_links(document, matcher, newlines)
            return True

    def store_text_citation_links(self, document, matcher, newlines):
        """Transform extracted citations from text into CitationLink objects."""
        citations = [self.make_citation(c, newlines) for c in matcher.citations]
        for c in citations:
            c.document = document
        document.citation_links.add(*citations, bulk=False)

    def make_citation(self, citation, newlines):
        """Adjust an extracted citation to take into account the fact that pdfjs_to_text adds newlines."""
        # get this page's newline indexes
        newlines = newlines[citation.target_id]

        citation.start = citation.start - bisect_left(newlines, citation.start)
        citation.end = citation.end - bisect_left(newlines, citation.end)
        if citation.prefix:
            citation.prefix = citation.prefix.replace("\n", "")
        if citation.suffix:
            citation.suffix = citation.suffix.replace("\n", "")

        citation = CitationLink.from_extracted_citation(citation)
        return citation


class CitatorMatcher:
    """Matcher that delegates to the Citator service."""

    citator_url = settings.PEACHJAM["CITATOR_API"]
    citator_key = settings.PEACHJAM["CITATOR_API_KEY"]
    max_text_size = 1024 * 1024 * 2

    def __init__(self):
        # extracted citations
        self.citations = []

    def markup_html_matches(self, frbr_uri, html):
        html_text = lxml.html.tostring(html, encoding="unicode")
        resp = self.call_citator(
            {
                "frbr_uri": frbr_uri.expression_uri(),
                "format": "html",
                "body": html_text,
            }
        )
        # returned the new, marked up, html
        return lxml.html.fromstring(resp["body"])

    def extract_text_matches(self, frbr_uri, text):
        # Only extract citations from the first 2MB of text. In practice, this impacts only very large gazettes
        # from SA.
        # Size distribution of gazettes:
        # - over 1MB: 1000
        # - over 2MB: 306
        # - over 5MB: 112
        if len(text) > self.max_text_size:
            log.info(
                f"Limiting to first {self.max_text_size} bytes of text (actual size: {len(text)} bytes)"
            )
            text = text[: self.max_text_size]

        resp = self.call_citator(
            {
                "frbr_uri": frbr_uri.expression_uri(),
                "format": "text",
                "body": text,
            }
        )
        # store the extracted citations
        self.citations = [
            ExtractedCitation(
                c["text"],
                c["start"],
                c["end"],
                c["href"],
                c["target_id"],
                c["prefix"],
                c["suffix"],
            )
            for c in resp["citations"]
        ]

    def call_citator(self, body):
        headers = {"Authorization": f"token {self.citator_key}"}
        resp = requests.post(self.citator_url, json=body, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()


citation_analyser = CitationAnalyser()
