from collections import defaultdict

from lxml import html


def generate_toc_json_from_html(root):
    """Parse content_html and generate a TOC from it. Updates content_html to ensure that TOC entries
    are enclosed in <div> tags so that they can be managed as a block.
    """
    items = []
    stack = []
    counts = defaultdict(int)
    ids = set()

    for heading in root.xpath("//h1 | //h2 | //h3 | //h4 | //h5"):
        if not heading.text_content():
            continue

        # no id, or it's a dup
        if "id" not in heading.attrib or heading.attrib["id"] in ids:
            tag_name = heading.tag
            counts[tag_name] += 1
            heading.attrib["id"] = f"{tag_name}_{counts[tag_name]}"
            ids.add(heading.attrib["id"])

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


def wrap_toc_entries_in_divs(root, toc):
    """Ensure the HTML covered by these TOC items are wrapped in nested divs. This may be run multiple times as a
    document gets edited, and so we want to handle the case where the divs are already present."""

    def wrap_items(items):
        for i, item in enumerate(items):
            next_item = items[i + 1] if i + 1 < len(items) else None
            next_id = next_item["id"] if next_item else None
            el = root.get_element_by_id(item["id"])

            if el is not None and el.tag != "div":
                wrapper = html.Element("div", id=item["id"])
                el.attrib.pop("id", None)
                el.addprevious(wrapper)

                # wrap all content from this heading to the next in a div
                # keep going until we run out of elements, or we hit the next TOC item
                node = el
                while node is not None and (
                    next_id is None or node.attrib.get("id") != next_id
                ):
                    next_node = node.getnext()
                    wrapper.append(node)
                    node = next_node

                if item["children"]:
                    wrap_items(item["children"])

    wrap_items(toc)
