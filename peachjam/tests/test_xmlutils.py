from unittest import TestCase

from peachjam.xmlutils import get_following_text, get_preceding_text, parse_html_str


class WrapTextTestCase(TestCase):
    def check_pre(self, xml, expected, max_chars=None):
        """Check that the given XML has the expected text."""
        tree = parse_html_str(xml)
        self.assertEqual(
            expected, get_preceding_text(tree.xpath("//a")[0], ["p"], max_chars)
        )

    def test_preceding_text(self):
        self.check_pre("<a>baz</a>", "")
        self.check_pre("<p><a>baz</a></p>", "")
        self.check_pre("<div><p>foo bar <a>baz</a></p></div>", "foo bar ")
        self.check_pre(
            "<div><p>foo bar <b>x <i>yy </i></b><a>baz</a></p></div>", "foo bar x yy "
        )
        self.check_pre(
            "<div><p>foo bar <b>x <i>yy </i></b>z<b>x <span>z <a>baz</a>tail</span></b></p>tail</div>",
            "foo bar x yy zx z ",
        )
        self.check_pre(
            "<div><section>xxx <p>foo bar <a>baz</a></p></section></div>", "foo bar "
        )

    def test_preceding_text_max_chars(self):
        self.check_pre("<div><p>foo bar <a>baz</a></p></div>", "bar ", 4)
        self.check_pre(
            "<div><p>foo bar <b>x <i>yy </i></b><a>baz</a></p></div>", "x yy ", 5
        )
        self.check_pre(
            "<div><p>foo bar <b>x <i>yy </i></b>z<b>x <span>z <a>baz</a>tail</span></b></p>tail</div>",
            "y zx z ",
            7,
        )
        self.check_pre(
            "<div><section>xxx <p>foo bar <a>baz</a></p></section></div>", "bar ", 4
        )

    def check_fol(self, xml, expected, max_chars=None):
        """Check that the given XML has the expected following text."""
        tree = parse_html_str(xml)
        self.assertEqual(
            expected, get_following_text(tree.xpath("//a")[0], ["p"], max_chars)
        )

    def test_following_text(self):
        self.check_fol("<a>baz</a>", "")
        self.check_fol("<p><a>baz</a></p>", "")
        self.check_fol("<div><p><a>baz</a> foo bar</p></div>", " foo bar")
        self.check_fol(
            "<div><p><a>baz</a><b>x <i>yy </i></b>foo bar</p></div>", "x yy foo bar"
        )
        self.check_fol(
            "<div><p><span><a>baz</a>z<b>x <span>z tail</span></b></span></p>outer</div>",
            "zx z tail",
        )
        self.check_fol(
            "<div><section><p><a>baz</a>foo bar</p>xxx</section></div>", "foo bar"
        )

    def test_following_text_max_chars(self):
        self.check_fol("<div><p><a>baz</a> foo bar</p></div>", " foo", 4)
        self.check_fol(
            "<div><p><a>baz</a><b>x <i>yy </i></b>foo bar</p></div>", "x yy ", 5
        )
        self.check_fol(
            "<div><p><span><a>baz</a>z<b>x <span>z tail</span></b></span></p>outer</div>",
            "zx z t",
            6,
        )
        self.check_fol(
            "<div><section><p><a>baz</a>foo bar</p>xxx</section></div>", "foo", 3
        )
