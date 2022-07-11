import shutil
import tempfile

import lxml.html
from docpipe.pdf import pdf_to_text

from peachjam.models import CitationLink


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
