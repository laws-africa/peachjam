from typing import List

import lxml.html

html_parser = lxml.html.HTMLParser(encoding="utf-8")


def parse_html_str(html) -> lxml.html.HtmlElement:
    """Encode HTML into utf-8 bytes and parse."""
    return lxml.html.fromstring(html.encode("utf-8"), parser=html_parser)


def strip_remarks(root: lxml.html.HtmlElement):
    """Removes akn-remark elements from the HTML tree."""
    for remark in root.xpath("//*[@class='akn-remark']"):
        remark.getparent().remove(remark)


def get_preceding_text(
    node: lxml.html.HtmlElement, not_above: List[str], max_chars: int = None
) -> str:
    """Get all the text preceding the given node (up to max_chars, if  given), but not going above the elements
    named in not_above."""
    parts = []
    length = 0

    def collect(text):
        """Append text to parts and update length."""
        nonlocal length
        parts.append(text)
        length += len(text)

    def collect_preceding_siblings(n):
        """Collect all text from siblings that precede node n."""
        prev = n.getprevious()
        while prev is not None:
            collect("".join(prev.itertext()) + (prev.tail or ""))
            prev = prev.getprevious()

    current = node
    while current is not None:
        # Collect any text before the current node in its parent
        collect_preceding_siblings(current)

        # get the text at the start of the parent
        parent = current.getparent()
        if parent and parent.text:
            collect(parent.text)

        # include text at the end of the current node
        if current != node and current.tail:
            collect(current.tail)

        # Stop if we've reached a tag we're not supposed to go above, or if we have enough text
        if (parent is not None and parent.tag in not_above) or (
            max_chars is not None and length >= max_chars
        ):
            break

        current = parent

    text = "".join(reversed(parts))
    if max_chars is not None:
        text = text[-max_chars:]

    return text


def get_following_text(
    node: lxml.html.HtmlElement, not_above: List[str], max_chars: int = None
) -> str:
    """Get all the text following the given node (up to max_chars, if given), but not going above the elements named
    in not_above."""
    parts = []
    length = 0

    def collect(text):
        """Append text to parts and update length."""
        nonlocal length
        parts.append(text)
        length += len(text)

    def collect_following_siblings(n):
        """Collect all text from siblings that follow node n."""
        next_sibling = n.getnext()
        while next_sibling is not None:
            collect("".join(next_sibling.itertext()) + (next_sibling.tail or ""))
            next_sibling = next_sibling.getnext()

    current = node
    while current is not None:
        if current.tail:
            collect(current.tail)

        # Collect any text after the current node in its parent
        collect_following_siblings(current)

        parent = current.getparent()

        # Stop if we've reached a tag we're not supposed to go above, or if we have enough text
        if (parent is not None and parent.tag in not_above) or (
            max_chars is not None and length >= max_chars
        ):
            break

        current = parent

    text = "".join(parts)
    if max_chars is not None:
        text = text[:max_chars]

    return text
