from dataclasses import dataclass

from lxml import etree

from peachjam.analysis.xmlutils import wrap_text


class TextPatternMatcher:
    """Logic for matching and marking up portions of text in paged text,  xml or html documents using regular
    expressions. It supports two modes of operation:

    1. running the regular expression across plain text, and storing the matches in citations.
    2. running the regular expression across certain nodes in an HTML/XML tree, marking up the matches, and storing
       matches in citations.
    """

    pattern_re = None
    """ Compiled re pattern to be applied to the text. Must be defined by subclasses.
    """

    candidate_xpath = ".//text()"
    """ Xpath for candidate text nodes that should be tested for matches. Defaults to all text nodes.
    """

    marker_tag = "mark"
    """ Tag that will be used to markup matches.
    """

    def setup(self, frbr_uri, text=None, root=None):
        self.frbr_uri = frbr_uri
        self.text = text
        self.root = root
        self.pagenum = None

        if root is not None:
            self.ns = self.root.nsmap[None] if self.root.nsmap else None
            self.nsmap = {"a": self.ns} if self.ns else {}
            self.marker_tag = (
                "{%s}%s" % (self.ns, self.marker_tag) if self.ns else self.marker_tag
            )
            self.candidate_xpath = etree.XPath(
                self.candidate_xpath, namespaces=self.nsmap
            )

    def extract_text_matches(self, frbr_uri, text):
        """Extract matches in plain text."""
        self.setup(frbr_uri, text=text)
        self.extract_paged_text_matches()

    def extract_paged_text_matches(self):
        # split on form feed (page break)
        for i, page in enumerate(self.text.split("\0xC")):
            self.pagenum = i
            self.run_text_extraction(page)

    def run_text_extraction(self, text):
        for match in self.find_text_matches(text):
            if self.is_text_match_valid(text, match):
                self.handle_text_match(text, match)

    def find_text_matches(self, text):
        """Return an iterable of matches in this chunk of text."""
        return self.pattern_re.finditer(text)

    def is_text_match_valid(self, text, match):
        return True

    def handle_text_match(self, text, match):
        pass

    def markup_html_matches(self, frbr_uri, root):
        """Extract matches in a parsed HTML tree."""
        self.setup(frbr_uri, root=root)
        self.run_html_matching()

    def run_html_matching(self):
        for ancestor in self.ancestor_nodes():
            for candidate in self.candidate_text_nodes(ancestor):
                node = candidate.getparent()

                # TODO: this could probably be made simpler if we processed matches from right to left.
                if not candidate.is_tail:
                    # text directly inside a node
                    for match in self.find_text_matches(node.text):
                        new_node = self.handle_node_match(node, match, in_tail=False)
                        if new_node is not None:
                            # the node has now changed, making the offsets in any subsequent
                            # matches incorrect. so stop looking and start again, checking
                            # the tail of the newly inserted node
                            node = new_node
                            break

                while node is not None and node.tail:
                    for match in self.find_text_matches(node.tail):
                        new_node = self.handle_node_match(node, match, in_tail=True)
                        if new_node is not None:
                            # the node has now changed, making the offsets in any subsequent
                            # matches incorrect. so stop looking and start again, checking
                            # the tail of the newly inserted node
                            node = new_node
                            break
                    else:
                        # we didn't break out of the loop, so there are no valid matches, give up
                        node = None

    def handle_node_match(self, node, match, in_tail):
        """Process a match. If this modifies the text (or tail, if in_tail is True), then
        return the new node that should have its tail checked for further matches.
        Otherwise, return None.
        """
        if self.is_node_match_valid(node, match):
            marker, start_pos, end_pos = self.markup_node_match(node, match)
            return wrap_text(node, in_tail, lambda t: marker, start_pos, end_pos)

    def is_node_match_valid(self, node, match):
        return True

    def markup_node_match(self, node, match):
        """Create a markup element for a match.

        Returns an (element, start_pos, end_pos) tuple.

        The element is the new element to insert into the tree, and the start_pos and end_pos specify
        the offsets of the chunk of text that will be replaced by the new element.
        """
        marker = etree.Element(self.marker_tag)
        marker.text = match.group(0)
        return marker, match.start(0), match.end(0)

    def ancestor_nodes(self):
        return [self.root]

    def candidate_text_nodes(self, root):
        return self.candidate_xpath(root)


@dataclass
class ExtractedCitation:
    text: str
    start: int
    end: int
    href: str
    target_id: str


class CitationMatcher(TextPatternMatcher):
    """Marks references to cited documents that follow a common citation pattern."""

    marker_tag = "a"

    href_pattern = "/akn/"

    def setup(self, *args, **kwargs):
        super().setup(*args, **kwargs)
        self.citations = []

    def handle_text_match(self, text, match):
        self.citations.append(
            ExtractedCitation(
                match.group(),
                match.start(),
                match.end(),
                self.make_href(match),
                self.pagenum,
            )
        )

    def is_node_match_valid(self, node, match):
        if self.make_href(match) != self.frbr_uri.work_uri():
            return True

    def markup_node_match(self, node, match):
        """Markup the match with a ref tag. The first group in the match is substituted with the ref."""
        node, start, end = super().markup_node_match(node, match)
        href = self.make_href(match)
        node.set("href", href)
        self.citations.append(
            ExtractedCitation(match.group(), match.start(), match.end(), href)
        )
        return node, start, end

    def make_href(self, match):
        """Turn this match into a full FRBR URI href using the href_pattern. Subclasses can also
        override this method to do more complex things.
        """
        return self.href_pattern.format(**self.href_pattern_args(match))

    def href_pattern_args(self, match):
        return match.groupdict()
