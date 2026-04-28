OFFENCE_CATEGORY_NAMES = (
    "Violence",
    "Sexual and Gender-Based Violence",
    "Property",
    "Financial and Economic",
    "Public Order",
    "State and Political",
    "Justice System",
    "Public Safety",
    "Morality",
)

OFFENCE_TAGS = (
    "child-targeted",
    "deception-based",
    "weapon-capable",
    "consent-related",
    "custody-related",
    "public-official-related",
    "omission-based",
    "inchoate",
)

JUDGMENT_OFFENCE_CASE_TAGS = (
    "child-victim",
    "domestic-context",
    "intimate-partner-context",
    "public-official-victim",
    "multiple-victims",
    "weapon-used",
    "group-offending",
    "serious-injury",
    "fatality",
    "threats-used",
    "trust-relationship",
    "deception-used",
    "identification-issue",
    "confession-issue",
    "circumstantial-evidence",
    "consent-disputed",
)


def normalize_tag_array(tags, allowed_tags=None, validate=False):
    allowed_set = set(allowed_tags or [])
    cleaned = []
    seen = set()
    invalid = []

    for tag in tags or []:
        normalized = (tag or "").strip().lower()

        if not normalized or normalized in seen:
            continue

        if allowed_tags is not None and normalized not in allowed_set:
            invalid.append(normalized)
            continue

        cleaned.append(normalized)
        seen.add(normalized)

    if validate and invalid:
        raise ValueError("Unknown tags: %s" % ", ".join(invalid))

    return cleaned
