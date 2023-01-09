import shutil
import tempfile
from bisect import bisect_left

import lxml.html

from peachjam.helpers import pdfjs_to_text
from peachjam.models import CitationLink


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
            matcher().markup_html_matches(document.expression_uri(), html)
        document.content_html = lxml.html.tostring(html, encoding="unicode")
        return True

    def extract_citations_from_source_file(self, document):
        if not hasattr(document, "source_file"):
            return False

        with tempfile.NamedTemporaryFile() as tmp:
            # convert document to pdf and then extract the text
            pdf = document.source_file.as_pdf()
            shutil.copyfileobj(pdf, tmp)
            tmp.flush()
            text = self.pdf_to_text(tmp.name)

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

    def pdf_to_text(self, fname):
        return pdfjs_to_text(fname)


citation_analyser = CitationAnalyser()
