import shutil
import tempfile
from dataclasses import dataclass

import lxml.html
from docpipe.pdf import pdf_to_text

from peachjam.analysis.matchers import TextPatternMatcher
from peachjam.models import CitationLink


@dataclass
class ExtractedCitation:
    text: str
    start: int
    end: int
    href: str
    target_id: str


class CitationMatcher(TextPatternMatcher):
    """Marks references to cited documents that follow a common citation pattern."""

    marker_tag = "a"

    href_pattern = "/akn/"

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.citations = []

    def handle_text_match(self, text, match):
        self.citations.append(
            ExtractedCitation(
                match.group(),
                match.start(),
                match.end(),
                self.make_href(match),
                self.pagenum,
            )
        )

    def is_node_match_valid(self, node, match):
        if self.make_href(match) != self.frbr_uri.work_uri():
            return True

    def markup_node_match(self, node, match):
        """Markup the match with a ref tag. The first group in the match is substituted with the ref."""
        node, start, end = super().markup_node_match(node, match)
        href = self.make_href(match)
        node.set("href", href)
        self.citations.append(
            ExtractedCitation(match.group(), match.start(), match.end(), href)
        )
        return node, start, end

    def make_href(self, match):
        """Turn this match into a full FRBR URI href using the href_pattern. Subclasses can also
        override this method to do more complex things.
        """
        return self.href_pattern.format(**self.href_pattern_args(match))

    def href_pattern_args(self, match):
        return match.groupdict()


class CitationAnalyser:
    matchers = []

    def extract_citations(self, document):
        """Run matchers across the HTML or text in this document."""
        if document.content_html_is_akn:
            # don't markup AKN HTML
            return

        if document.content_html:
            # markup html
            self.extract_citations_from_html(document)
        else:
            # markup the source file by extracting the text and assuming we'll render it as a PDF
            self.extract_citations_from_source_file(document)

    def extract_citations_from_html(self, document):
        html = lxml.html.fromstring(document.content_html)
        for matcher in self.matchers:
            matcher.markup_html_matches(document.expression_uri(), html)
        document.content_html = lxml.html.tostring(html, encoding="unicode")

    def extract_citations_from_source_file(self, document):
        if not hasattr(document, "source_file"):
            return

        with tempfile.NamedTemporaryFile() as tmp:
            # convert document to pdf and then extract the text
            pdf = document.source_file.as_pdf()
            shutil.copyfileobj(pdf, tmp)
            tmp.flush()
            text = pdf_to_text(tmp.name)

        for matcher in self.matchers:
            matcher = matcher()
            matcher.extract_text_matches(document.expression_uri(), text)
            self.store_text_citation_links(document, matcher)

    def store_text_citation_links(self, document, matcher):
        """Transform extracted citations from text into CitationLink objects."""
        citations = [CitationLink.from_extracted_citation(c) for c in matcher.citations]
        for c in citations:
            c.document = document
        document.citation_links.add(*citations, bulk=False)


citation_analyser = CitationAnalyser()
