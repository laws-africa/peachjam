from collections import defaultdict

from docpipe.pipeline import Pipeline, PipelineContext, Stage


class CitationContext(PipelineContext):
    document = None
    """Document being processed."""
    html = None
    """Parsed HTML."""
    html_text = None
    """Extracted HTML in text format. """
    text = None
    """Extracted text. """
    use_html = False
    """Use HTML rather than text? """
    citation_links = []
    """Extracted citation links that must be stored. """


class ExtractHtml(Stage):
    """Extract HTML from the document into html_text.

    Reads: document.content_html
    Writes: html_text
    """

    def __call__(self, context):
        context.html_text = context.document.content_html


class ReplaceHtml(Stage):
    """Replace the context HTML text back into the document.

    Reads: html_text
    Writes: document.content_html
    """

    def __call__(self, context):
        context.document.content_html = context.document.content_html


class ExtractPDFText(Stage):
    """Extract the text content from the document by first converting it to a PDF.

    Reads: document.source_file
    Writes: document.text
    """

    def __call__(self, context):
        #  TODO: call soffice_convert
        context.document.text = "extracted text^Lwith page breaks"


class StoreCitations(Stage):
    """Store the extracted citations as CitationLink objects.

    Reads: citations
    Writes: document.citation_links
    """

    def __call__(self, context):
        # TODO: who builds citation objects?
        context.document.citation_links.add(context.citation_links)


class CitationAnalyser:
    pipelines = defaultdict(list)
    """A dict from pipeline name to a list of pipelines."""

    def get_pipelines(self, name, expression_uri):
        """Get a named pipeline, if any, that is suitable for this expression_uri."""
        # TODO: take expression_uri into account
        # TODO: plugins
        return self.pipelines.get(name)

    def extract_citations(self, document):
        pipelines = self.get_pipelines("citations", document.expression_uri)
        if not pipelines:
            return

        if document.content_html_is_akn:
            # don't markup AKN HTML
            return

        pipeline = Pipeline()
        context = CitationContext(pipeline=pipeline)
        context.document = document

        if document.content_html:
            # markup html
            context.use_html = True
            pipeline.stages = [
                ExtractPDFText(),
                Pipeline(pipelines),
                StoreCitations(),
            ]
        else:
            # markup the source file by extracting the text and assuming we'll render it as a PDF
            pipeline.stages = [
                ExtractHtml(),
                Pipeline(pipelines),
                ReplaceHtml(),
            ]

        pipeline(context)


citation_analyser = CitationAnalyser()
