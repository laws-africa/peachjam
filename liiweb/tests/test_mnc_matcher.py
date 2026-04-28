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
        html = lxml.html.fromstring("""
<div>
  <p>2 Commissioner for the South African Revenue Service v Toneleria Nacional RSA (Pty) Ltd [2021] ZASCA 65; [2021] 3 All SA 299 (SCA); 2021 (5) SA 68 (SCA) para 25.</p>
  <p>Kenya: [2022] KESC 12</p>
  <p>Some string that has [2021] code 65</p>
  <p>Some string that has [2021] code 6-5a</p>
  <p>Some string that has [2021] ZA SC 6</p>
  <p>A place that isn't trusted [1988] XXCC 12.</p>
</div>
""")  # noqa
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
        html = lxml.html.fromstring("""
<div>
  <p>see, Grundler N.O. and Another v Zulu and Another (D8029/2021) [2023] ZAKZDHC 7 (20 February 2023).</p>
  <p>ted in Motshegoa v Motshegoa and Another (995/98) [2000] ZANWHC 6 (11 May 2000) at p19:</p>
</div>
""")  # noqa
        self.marker.markup_html_matches(self.frbr_uri, html)

        self.assertMultiLineEqual(
            """<div>
  <p>see, Grundler N.O. and Another v Zulu and Another (D8029/2021) <a href="/akn/za-kzn/judgment/zakzdhc/2023/7">[2023] ZAKZDHC 7</a> (20 February 2023).</p>
  <p>ted in Motshegoa v Motshegoa and Another (995/98) <a href="/akn/za-nw/judgment/zanwhc/2000/6">[2000] ZANWHC 6</a> (11 May 2000) at p19:</p>
</div>""",  # noqa
            lxml.html.tostring(html, encoding="unicode", pretty_print=True).strip(),
        )

    def test_gh_sc_mismatch(self):
        # In Ghana, "[2011] 1 SCGLR 505" is a law report, not a seychelles court
        self.frbr_uri = FrbrUri.parse("/akn/gh/judgment/ghsc/2025/509")
        html = lxml.html.fromstring("""
<div>
  <p>In Amoah v. Lokko &amp; Afred Quartey (substituted by) Gloria Quartey [2011] SCGLR 505, his Lordship Aryeetey JSC had this to say;</p>
</div>
""")  # noqa
        self.marker.markup_html_matches(self.frbr_uri, html)

        self.assertMultiLineEqual(
            """<div>
  <p>In Amoah v. Lokko &amp; Afred Quartey (substituted by) Gloria Quartey [2011] SCGLR 505, his Lordship Aryeetey JSC had this to say;</p>
</div>""",  # noqa
            lxml.html.tostring(html, encoding="unicode", pretty_print=True).strip(),
        )

    def test_text_matches(self):
        self.marker.extract_text_matches(
            self.frbr_uri,
            """
In other words, what is not pleaded ought not to beconsidered by the trial or appellate court. See Parvis Gulamali
Fazal v. National Housing Corporation (Civil Appeal No. 166 of 2018) [2021]TZCA 738 (3 December 2021, TanzLII), Maria
Amandus Kavishe v. Nora Waziri Mzeru and Another (Civil Appeal No. 365 of 2019) [2023] TZCA 31 (20 February 2023,
TanzLII) and Charles Richard Kombe t/a Building v. Eva rani Mtungi (Civil Appeal No. 38 of 2012) [2017] TZCA153 (24
March 2017, TanzLII) to mention a few
        """,
        )
        self.assertEqual(
            [
                ("[2021]TZCA 738", "/akn/tz/judgment/tzca/2021/738"),
                ("[2023] TZCA 31", "/akn/tz/judgment/tzca/2023/31"),
                ("[2017] TZCA153", "/akn/tz/judgment/tzca/2017/153"),
            ],
            [(c.text, c.href) for c in self.marker.citations],
        )
