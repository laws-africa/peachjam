# flake8: noqa
from unittest import TestCase

import lxml
from cobalt import FrbrUri

from africanlii.analysis import RefsMarkerAchprResolutions


class RefsMarkerAchprResolutionsTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.marker = RefsMarkerAchprResolutions()
        self.frbr_uri = FrbrUri.parse("/akn/aa-au/statement/resolution/achpr/2021/509")

    def test_simple_matches(self):
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
