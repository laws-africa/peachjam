import logging
from bisect import bisect_left

import lxml.html
import requests
from cobalt import FrbrUri
from django.conf import settings
from django.utils.text import Truncator
from docpipe.matchers import ExtractedCitation
from lxml import html
from lxml.etree import ParseError

from peachjam.models import CitationLink, ExtractedCitationContext

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
        try:
            html = document.content_html_tree
        except ParseError as e:
            log.warning(
                f"Could not parse HTML for document {document.expression_uri()}: {document.content_html}",
                exc_info=e,
            )
            return False

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

    def update_citation_contexts(self, document):
        if document.content_html:
            self.create_from_html(document)
        else:
            self.create_from_citation_links(document)

    def get_provision_eid(self, url):
        for sep in ("~", "#"):
            if sep in url:
                return url.split(sep, 1)[1]
        return None

    def create_from_html(self, document):
        """Create citation contexts from an HTML document."""
        from peachjam.models import Work

        def get_parent_element(anchor, tags=("p", "div", "section")):
            current = anchor
            while current is not None:
                if current.tag in tags:
                    return current
                current = current.getparent()
            return None

        if not document.content_html:
            log.warning("No HTML content to extract citation contexts from.")
            return

        root = html.fromstring(document.content_html)
        if document.content_html_is_akn:
            xpath = (
                '//*[contains(@class, "akn-akomaNtoso")]//a[starts-with(@data-href, "/akn") and '
                'not(ancestor::*[contains(@class, "akn-remark")])]'
            )
            attr = "data-href"
        else:
            xpath = '//a[starts-with(@href, "/akn")]'
            attr = "href"

        for a in root.xpath(xpath):
            try:
                href = a.attrib[attr]
                log.info("Processing citation link %s in document %s", href, document)
                work_frbr_uri = FrbrUri.parse(href).work_uri()
                work = Work.objects.get(frbr_uri=work_frbr_uri)
                exact = a.text_content().strip()
                parent_element = get_parent_element(a)
                parent_text = parent_element.text_content().strip()
                start = parent_text.find(exact)
                end = start + len(exact)
                if start == -1:
                    continue
                prefix = Truncator(parent_text[:start]).chars(100, truncate="")
                suffix = Truncator(parent_text[end:]).chars(100, truncate="")

                selector_id = parent_element.attrib.get("id", "")

                ctx = ExtractedCitationContext.objects.create(
                    document=document,
                    selectors=[
                        {
                            "type": "TextPositionSelector",
                            "start": start,
                            "end": end,
                        },
                        {
                            "type": "TextQuoteSelector",
                            "exact": exact,
                            "prefix": prefix,
                            "suffix": suffix,
                        },
                    ],
                    selector_anchor_id=selector_id,
                    target_work=work,
                    target_provision_eid=self.get_provision_eid(href),
                )
                log.info("Created citation context %s for document %s", ctx, document)
            except ValueError as e:
                log.warning(
                    "Invalid FRBR URI in citation link %s in document %s: %s",
                    a.attrib[attr],
                    document,
                    e,
                )
            except Work.DoesNotExist:
                log.warning(
                    "No work found for FRBR URI %s in document %s",
                    a.attrib[attr],
                    document,
                )

    def create_from_citation_links(self, document):
        """Create a citation context from an existing CitationLink."""
        from peachjam.models import Work

        for citation_link in CitationLink.objects.filter(document=document):

            try:
                url = citation_link.url
                frbr_uri = FrbrUri.parse(url).work_uri()
                target_work = Work.objects.get(frbr_uri=frbr_uri)
                ExtractedCitationContext.objects.create(
                    document=document,
                    selector_anchor_id=citation_link.target_id,
                    selectors=citation_link.target_selectors,
                    target_work=target_work,
                    target_provision_eid=self.get_provision_eid(citation_link.url),
                )
            except ValueError as e:
                log.warning(
                    "Invalid FRBR URI in citation link %s in document %s: %s",
                    citation_link.url,
                    document,
                    e,
                )
            except Work.DoesNotExist:
                log.warning(
                    "No work found for FRBR URI %s in document %s",
                    citation_link.url,
                    document,
                )


class CitatorMatcher:
    """Matcher that delegates to the Citator service."""

    citator_url = settings.PEACHJAM["CITATOR_API"]
    citator_key = settings.PEACHJAM["LAWSAFRICA_API_KEY"]
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

        # For text documents, we need to provide the existing citations for context. For html, existing citations
        # are already marked up in the HTML.
        citations = [
            c.to_citator_api()
            for c in CitationLink.objects.filter(
                document__expression_frbr_uri=frbr_uri.expression_uri()
            )
        ]

        resp = self.call_citator(
            {
                "frbr_uri": frbr_uri.expression_uri(),
                "format": "text",
                "body": text,
                "citations": citations,
            }
        )

        # only keep new citations
        existing = {(c["start"], c["end"]) for c in citations}
        citations = [
            c for c in resp["citations"] if (c["start"], c["end"]) not in existing
        ]

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
            for c in citations
        ]

    def call_citator(self, body):
        headers = {"Authorization": f"token {self.citator_key}"}
        resp = requests.post(
            self.citator_url, json=body, headers=headers, timeout=60 * 10
        )
        resp.raise_for_status()
        return resp.json()


citation_analyser = CitationAnalyser()
