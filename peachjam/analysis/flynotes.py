import logging
import re

from django.utils.html import strip_tags
from django.utils.text import slugify

from peachjam.models.settings import pj_settings
from peachjam.models.taxonomies import DocumentTopic, Taxonomy

log = logging.getLogger(__name__)


def parse_flynote_text(text):
    if not text:
        return []

    text = strip_tags(text).strip()
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip().rstrip(".")

    if not text:
        return []

    dash_pattern = r"\s*[\u2014\u2013]\s*|\s+[-\u2010\u2011\u2012]\s+"
    if not re.search(dash_pattern, text):
        return []

    segments = [s.strip() for s in text.split(";") if s.strip()]

    current_path = []
    paths = []

    for segment in segments:
        parts = [p.strip() for p in re.split(dash_pattern, segment) if p.strip()]
        if not parts:
            continue

        n = len(parts)
        if not current_path:
            current_path = parts
        else:
            current_path = current_path[: max(len(current_path) - n, 0)] + parts

        paths.append(list(current_path))

    return paths


def normalise_flynote_name(name):
    return slugify(name)


def get_or_create_taxonomy_node(parent, name):

    children = parent.get_children() if parent else Taxonomy.get_root_nodes()
    normalised = normalise_flynote_name(name)
    for child in children:
        if normalise_flynote_name(child.name) == normalised:
            return child

    if parent:
        return parent.add_child(name=name)
    else:
        return Taxonomy.add_root(name=name)


def update_flynote_taxonomy_for_judgment(judgment):

    settings = pj_settings()
    root = settings.flynote_taxonomy_root
    if not root:
        log.warning("No flynote taxonomy root configured, skipping.")
        return

    flynote_descendant_ids = set(root.get_descendants().values_list("pk", flat=True))
    DocumentTopic.objects.filter(
        document=judgment, topic_id__in=flynote_descendant_ids
    ).delete()

    paths = parse_flynote_text(judgment.flynote)
    if not paths:
        return

    leaf_topics = set()
    for path in paths:
        current_parent = root
        for name in path:
            current_parent = get_or_create_taxonomy_node(current_parent, name)
        leaf_topics.add(current_parent)

    for topic in leaf_topics:
        DocumentTopic.objects.get_or_create(document=judgment, topic=topic)

    log.info(
        f"Linked judgment {judgment.pk} to {len(leaf_topics)} flynote taxonomy topics."
    )
