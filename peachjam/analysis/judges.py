import re
import unicodedata

from django.db import transaction
from django.utils.text import slugify

TITLE_TOKENS = {
    "ACJ",
    "ACTJ",
    "AJ",
    "AJP",
    "AJA",
    "AP",
    "CJ",
    "CM",
    "DCJ",
    "J",
    "JA",
    "JCC",
    "JP",
    "PM",
    "P",
    "R",
    "SCJ",
    "SCM",
}

PUNCTUATION_PATTERN = re.compile(r"[.,;:()]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^0-9A-Za-z]+")


def normalize_judge_name(value):
    value = unicodedata.normalize("NFKC", value or "")
    value = value.strip()
    value = value.replace(".", "")
    value = PUNCTUATION_PATTERN.sub(" ", value)
    value = value.replace("-", " ")
    value = NON_ALNUM_PATTERN.sub(" ", value)
    value = WHITESPACE_PATTERN.sub(" ", value)
    return value.casefold().strip()


def parse_judge_name(value):
    """This splits a source judge string into raw, normalized, canonical, and title parts.

    Example: ``ABBAN, J.A.`` becomes raw_name ``ABBAN, J.A.``, normalized_name
    ``abban ja``, base_name ``abban``, and title ``JA``.
    """
    raw_name = (value or "").strip()
    normalized_name = normalize_judge_name(raw_name)
    tokens = normalized_name.split()
    title = ""
    if tokens:
        candidate_title = tokens[-1].upper()
        if candidate_title in TITLE_TOKENS:
            title = candidate_title
            tokens = tokens[:-1]

    return {
        "raw_name": raw_name,
        "normalized_name": normalized_name,
        "base_name": " ".join(tokens).strip(),
        "title": title,
    }


def canonical_name_from_aliases(names):
    candidates = []
    for name in names:
        parts = parse_judge_name(name)
        base_name = parts["base_name"] or parts["normalized_name"]
        if not base_name:
            continue

        words = re.split(r"\s+", (name or "").strip())
        if parts["title"] and words:
            words = words[:-1]
        display_name = " ".join(words).strip(" ,.;:-")
        candidates.append(display_name or (name or "").strip())

    if not candidates:
        return "judge"

    return sorted(candidates, key=lambda value: (-len(value), value.casefold()))[0]


def unique_judge_slug(model, name, *, pk=None):
    base_slug = slugify(name) or "judge"
    slug = base_slug
    suffix = 2
    while True:
        qs = model.objects.filter(slug=slug)
        if pk:
            qs = qs.exclude(pk=pk)
        if not qs.exists():
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def merge_judges(primary_judge_person, duplicate_judges):
    from peachjam.models import Bench, JudgeAlias

    duplicate_judges = [
        duplicate
        for duplicate in duplicate_judges
        if duplicate.pk and duplicate.pk != primary_judge_person.pk
    ]
    if not duplicate_judges:
        return primary_judge_person

    with transaction.atomic():
        for duplicate in duplicate_judges:
            JudgeAlias.objects.filter(judge_person=duplicate).update(
                judge_person=primary_judge_person
            )
            Bench.objects.filter(judge_person=duplicate).update(
                judge_person=primary_judge_person
            )
            duplicate.delete()

    return primary_judge_person
