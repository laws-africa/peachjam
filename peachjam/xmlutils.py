import lxml.html

html_parser = lxml.html.HTMLParser(encoding="utf-8")


def parse_html_str(html) -> lxml.html.HtmlElement:
    """Encode HTML into utf-8 bytes and parse."""
    return lxml.html.fromstring(html.encode("utf-8"), parser=html_parser)


def strip_remarks(root: lxml.html.HtmlElement):
    """Removes akn-remark elements from the HTML tree."""
    for remark in root.xpath("//*[@class='akn-remark']"):
        remark.getparent().remove(remark)
