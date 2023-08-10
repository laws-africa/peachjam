from unittest import TestCase

import lxml.html
from cobalt.uri import FrbrUri

from liiweb.citations import MncMatcher


class MncMatcherTest(TestCase):
    maxDiff = None

    def setUp(self):
        self.marker = MncMatcher()
        self.frbr_uri = FrbrUri.parse("/akn/za-wc/act/2021/509")

    def test_html_matches(self):
        html = lxml.html.fromstring(
            """
<div>
  <p>2 Commissioner for the South African Revenue Service v Toneleria Nacional RSA (Pty) Ltd [2021] ZASCA 65; [2021] 3 All SA 299 (SCA); 2021 (5) SA 68 (SCA) para 25.</p>
  <p>Kenya: [2022] KESC 12</p>
  <p>Some string that has [2021] code 65</p>
  <p>Some string that has [2021] code 6-5a</p>
  <p>Some string that has [2021] ZA SC 6</p>
  <p>A place that isn't trusted [1988] XXCC 12.</p>
</div>
"""  # noqa
        )
        self.marker.markup_html_matches(self.frbr_uri, html)

        self.assertMultiLineEqual(
            """<div>
  <p>2 Commissioner for the South African Revenue Service v Toneleria Nacional RSA (Pty) Ltd <a href="/akn/za/judgment/zasca/2021/65">[2021] ZASCA 65</a>; [2021] 3 All SA 299 (SCA); 2021 (5) SA 68 (SCA) para 25.</p>
  <p>Kenya: <a href="/akn/ke/judgment/kesc/2022/12">[2022] KESC 12</a></p>
  <p>Some string that has [2021] code 65</p>
  <p>Some string that has [2021] code 6-5a</p>
  <p>Some string that has [2021] ZA SC 6</p>
  <p>A place that isn't trusted [1988] XXCC 12.</p>
</div>""",  # noqa
            lxml.html.tostring(html, encoding="unicode", pretty_print=True).strip(),
        )

    def test_za_provincial_matches(self):
        html = lxml.html.fromstring(
            """
<div>
  <p>see, Grundler N.O. and Another v Zulu and Another (D8029/2021) [2023] ZAKZDHC 7 (20 February 2023).</p>
  <p>ted in Motshegoa v Motshegoa and Another (995/98) [2000] ZANWHC 6 (11 May 2000) at p19:</p>
</div>
"""  # noqa
        )
        self.marker.markup_html_matches(self.frbr_uri, html)

        self.assertMultiLineEqual(
            """<div>
  <p>see, Grundler N.O. and Another v Zulu and Another (D8029/2021) <a href="/akn/za-kzn/judgment/zakzdhc/2023/7">[2023] ZAKZDHC 7</a> (20 February 2023).</p>
  <p>ted in Motshegoa v Motshegoa and Another (995/98) <a href="/akn/za-nw/judgment/zanwhc/2000/6">[2000] ZANWHC 6</a> (11 May 2000) at p19:</p>
</div>""",  # noqa
            lxml.html.tostring(html, encoding="unicode", pretty_print=True).strip(),
        )
