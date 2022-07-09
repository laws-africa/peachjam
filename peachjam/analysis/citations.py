import lxml.html


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
            self.extract_citations_from_text(document)

    def extract_citations_from_html(self, document):
        html = lxml.html.fromstring(document.content_html)
        for matcher in self.matchers:
            matcher.markup_html_matches(document.expression_uri(), html)
        document.content_html = lxml.html.tostring(html, encoding="unicode")

    def extract_citations_from_text(self, document):
        #  TODO: call soffice_convert
        text = "extracted text^Lwith page breaks"
        for matcher in self.matchers:
            matcher = matcher()
            matcher.extract_text_matches(document.expression_uri(), text)
            self.store_citations(matcher)


citation_analyser = CitationAnalyser()
