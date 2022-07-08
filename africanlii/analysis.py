import re

from docpipe.pipeline import Pipeline, Stage

from peachjam.analysis.citations import citation_analyser
from peachjam.analysis.matchers import RefsMarker


class RefsMarkerAchprResolutions(RefsMarker):
    """Finds references to ACHPR resolutions in documents, of the form:

    ACHPR/Res.227 (LII) 2012
    """

    pattern_re = re.compile(
        r"""\bACHPR/Res\.\s*
            (\d+)\s*
            \([XVILC]\)\s*
            \((\d{2,4})\)
        """,
        re.X | re.I,
    )
    candidate_xpath = ".//text()[contains(., 'ACHPR') and not(ancestor::a:ref)]"


class CitationStage(Stage):
    def __init__(self, matcher, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matcher = matcher

    def __call__(self, context):
        if context.use_html:
            self.matcher.markup_html_matches(
                context.document.expression_uri(), context.html
            )
        else:
            self.matcher.extract_text_matches(
                context.document.expression_uri(), context.text
            )


citation_pipeline = Pipeline(
    [
        # TODO: achpr matcher, use whatever marker is appropriate
        # TODO: Act 5 of 2019 matcher, use whatever marker is appropriate
        # TODO: for plain text, we care about the regex and how to extract the right run and FRBR URI from it
        # TODO: for html, we care about the regex and how to markup the right run and FRBR URI from it
        CitationStage(RefsMarkerAchprResolutions())
    ]
)


# TODO: plugins
# TODO: how does the pipeline fit in with the markers?
# TODO: marker handles just xml (or html?), pipeline passes in xml root
citation_analyser.pipelines["enrichment"].append(citation_pipeline)
