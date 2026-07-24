import json
from dataclasses import asdict, dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SearchProfile:
    """Serializable text-search tuning values for SearchEngine."""

    name: str
    search_field_boosts: dict[str, float | int]
    phrase_match_content_boost: float | int
    phrase_match_slop: int
    simple_query_string_options: dict[str, Any]
    advanced_simple_query_string_options: dict[str, Any]
    provision_title_boost: float | int
    provision_parent_titles_boost: float | int
    use_pagerank_settings: bool
    pagerank_boost_value: float | None
    pagerank_pivot_value: float | None

    @classmethod
    def default(cls):
        """Load the required packaged default profile."""
        return get_default_search_profile_set().default

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class SearchProfileSet:
    """Default and per-query-label search profiles."""

    default: SearchProfile = field(default_factory=SearchProfile.default)
    labels: dict[str, SearchProfile] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        return cls(
            default=SearchProfile.from_dict(data["default"]),
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


def get_default_search_profile_set():
    """Load the packaged production profile set.

    Keeping this data beside the search code lets sites use tuned profiles
    without requiring a dependency on peachjam-pro.
    """
    path = files("peachjam_search").joinpath("search_profile_set.json")
    with path.open(encoding="utf-8") as f:
        return SearchProfileSet.from_dict(json.load(f))
