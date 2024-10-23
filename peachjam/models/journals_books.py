from collections import defaultdict

from django.db import models
from lxml import html
from martor.models import MartorField
from martor.utils import markdownify

from peachjam.models import CoreDocument
from peachjam.xmlutils import parse_html_str


class Book(CoreDocument):
    publisher = models.CharField(max_length=2048)
    content_markdown = MartorField(blank=True, null=True)
    default_nature = ("book", "Book")

    def delete_citations(self):
        super().delete_citations()
        # reset the HTML back to the original from markdown, because delete_citations()
        # removes any embedded akn links
        if self.content_markdown:
            self.convert_content_markdown()

    def convert_content_markdown(self):
        self.content_html = markdownify(self.content_markdown or "")
        self.update_toc_json_from_html()

    def update_toc_json_from_html(self):
        if self.content_html:
            root = parse_html_str(self.content_html or "")
            self.toc_json = self.generate_toc_json_from_html(root)
            self.wrap_toc_entries_in_divs(root)
            self.content_html = html.tostring(root, encoding="unicode")
        else:
            self.toc_json = []

    def generate_toc_json_from_html(self, root):
        """Parse content_html and generate a TOC from it. Updates content_html to ensure that TOC entries
        are enclosed in <div> tags so that they can be managed as a block.
        """
        items = []
        stack = []
        ids = defaultdict(int)

        for heading in root.xpath("//h1 | //h2 | //h3 | //h4 | //h5"):
            if not heading.text_content():
                continue

            if "id" not in heading.attrib:
                tag_name = heading.tag
                ids[tag_name] += 1
                heading.attrib["id"] = f"{tag_name}_{ids[tag_name]}"

            item = {
                "type": heading.tag,
                "title": heading.text_content(),
                "id": heading.attrib["id"],
                "children": [],
            }

            while stack and stack[-1]["type"] >= heading.tag:
                stack.pop()

            if stack:
                stack[-1]["children"].append(item)
            else:
                items.append(item)

            stack.append(item)

        return items

    def wrap_toc_entries_in_divs(self, root):
        def wrap_items(root, items):
            for i, item in enumerate(items):
                next_item = items[i + 1] if i + 1 < len(items) else None
                next_id = next_item["id"] if next_item else None
                el = root.get_element_by_id(item["id"])

                if el is not None:
                    wrapper = html.Element("div", id=item["id"])
                    el.attrib.pop("id", None)
                    el.addprevious(wrapper)

                    node = el
                    while node is not None and (
                        next_id is None or node.attrib.get("id") != next_id
                    ):
                        next_node = node.getnext()
                        wrapper.append(node)
                        node = next_node

                    if item["children"]:
                        wrap_items(wrapper, item["children"])

        wrap_items(root, self.toc_json)

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "book"
        self.doc_type = "book"
        return super().pre_save()


class Journal(CoreDocument):
    publisher = models.CharField(max_length=2048)
    default_nature = ("journal", "Journal")

    def pre_save(self):
        self.frbr_uri_doctype = "doc"
        self.frbr_uri_subtype = "journal"
        self.doc_type = "journal"
        return super().pre_save()
