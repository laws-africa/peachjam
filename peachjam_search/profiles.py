import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SEARCH_FIELD_BOOSTS = {
    "title": 8,
    "title_expanded": 3,
    "citation": 2,
    "alternative_names": 4,
    "content": 1,
    "summary": 2,
    "flynote": 2,
    "blurb": 2,
}

DEFAULT_SIMPLE_QUERY_STRING_OPTIONS = {
    "default_operator": "OR",
    "minimum_should_match": "4<80%",
}

DEFAULT_ADVANCED_SIMPLE_QUERY_STRING_OPTIONS = {
    "default_operator": "AND",
}

ADVANCED_ONLY_SEARCH_FIELDS = {
    "case_number": None,
    "case_name": None,
    "judges_text": None,
}


@dataclass(frozen=True)
class SearchProfile:
    """Serializable text-search tuning values for SearchEngine."""

    name: str = "default"
    search_field_boosts: dict[str, float | int] = field(
        default_factory=lambda: deepcopy(DEFAULT_SEARCH_FIELD_BOOSTS)
    )
    phrase_match_content_boost: float | int = 4
    phrase_match_slop: int = 0
    simple_query_string_options: dict[str, Any] = field(
        default_factory=lambda: deepcopy(DEFAULT_SIMPLE_QUERY_STRING_OPTIONS)
    )
    advanced_simple_query_string_options: dict[str, Any] = field(
        default_factory=lambda: deepcopy(DEFAULT_ADVANCED_SIMPLE_QUERY_STRING_OPTIONS)
    )
    provision_title_boost: float | int = 4
    provision_parent_titles_boost: float | int = 2
    use_pagerank_settings: bool = True
    pagerank_boost_value: float | None = None
    pagerank_pivot_value: float | None = None

    @classmethod
    def default(cls):
        return cls()

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def to_dict(self):
        return asdict(self)

    def build_search_fields(self):
        search_fields = {}
        for field_name, boost in self.search_field_boosts.items():
            if boost is None or float(boost) == 1.0:
                search_fields[field_name] = None
            else:
                search_fields[field_name] = {"boost": boost}
        return search_fields

    def build_advanced_search_fields(self):
        advanced_search_fields = dict(ADVANCED_ONLY_SEARCH_FIELDS)
        advanced_search_fields.update(self.build_search_fields())
        return advanced_search_fields


@dataclass(frozen=True)
class SearchProfileSet:
    """Default and per-query-label search profiles."""

    default: SearchProfile = field(default_factory=SearchProfile.default)
    labels: dict[str, SearchProfile] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        return cls(
            default=SearchProfile.from_dict(data.get("default", {})),
            labels={
                label: SearchProfile.from_dict(profile)
                for label, profile in data.get("labels", {}).items()
            },
        )

    @classmethod
    def from_json_path(cls, path):
        with Path(path).open(encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self):
        return {
            "default": self.default.to_dict(),
            "labels": {
                label: profile.to_dict() for label, profile in self.labels.items()
            },
        }

    def to_json_path(self, path):
        with Path(path).open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)
            f.write("\n")

    def get_profile(self, query_label=None):
        return self.labels.get(query_label) or self.default
