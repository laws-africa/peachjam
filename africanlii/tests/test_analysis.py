# flake8: noqa
from unittest import TestCase

import lxml.html
from cobalt import FrbrUri

from africanlii.analysis import AchprResolutionMatcher
from peachjam.analysis.matchers import ExtractedCitation


class RefsAchprResolutionMatcherTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.marker = AchprResolutionMatcher()
        self.frbr_uri = FrbrUri.parse("/akn/aa-au/statement/resolution/achpr/2021/509")

    def test_html_matches(self):
        html = lxml.html.fromstring(
            """
<div>
  <p><b>Recalling resolution</b> ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020, the Need to Prepare</p>
  <p><b>Recalling</b> its Resolution ACHPR/Res.79 (XXXVIII) 05 on the Composition and Operationalization</p>
</div>
"""
        )
        self.marker.markup_html_matches(self.frbr_uri, html)

        self.assertMultiLineEqual(
            """<div>
  <p><b>Recalling resolution</b> <a href="/akn/aa-au/statement/resolution/achpr/2020/437">ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020</a>, the Need to Prepare</p>
  <p><b>Recalling</b> its Resolution <a href="/akn/aa-au/statement/resolution/achpr/2005/79">ACHPR/Res.79 (XXXVIII) 05</a> on the Composition and Operationalization</p>
</div>""",
            lxml.html.tostring(html, encoding="unicode", pretty_print=True).strip(),
        )
        self.assertEqual(
            [
                ExtractedCitation(
                    "ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020",
                    1,
                    36,
                    "/akn/aa-au/statement/resolution/achpr/2020/437",
                ),
                ExtractedCitation(
                    "ACHPR/Res.79 (XXXVIII) 05",
                    16,
                    41,
                    "/akn/aa-au/statement/resolution/achpr/2005/79",
                ),
            ],
            self.marker.citations,
        )

    def test_text_matches(self):
        text = """
  Recalling resolution ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020, the Need to Prepare
  Recalling its Resolution ACHPR/Res.79 (XXXVIII) 05 on the Composition and Operationalization
"""
        self.marker.extract_text_matches(self.frbr_uri, text)

        self.assertEqual(
            [
                ExtractedCitation(
                    "ACHPR/Res. 437 (EXT.OS/ XXVI1) 2020",
                    24,
                    59,
                    "/akn/aa-au/statement/resolution/achpr/2020/437",
                ),
                ExtractedCitation(
                    "ACHPR/Res.79 (XXXVIII) 05",
                    108,
                    133,
                    "/akn/aa-au/statement/resolution/achpr/2005/79",
                ),
            ],
            self.marker.citations,
        )
