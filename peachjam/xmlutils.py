import lxml.html

html_parser = lxml.html.HTMLParser(encoding="utf-8")


def parse_html_str(html) -> lxml.html.HtmlElement:
    """Encode HTML into utf-8 bytes and parse."""
    return lxml.html.fromstring(html.encode("utf-8"), parser=html_parser)
