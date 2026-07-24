"""Run one SearchEngine query without recording a search trace."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from cobalt.uri import FrbrUri
from django.core.management.base import BaseCommand, CommandError
from django.http import QueryDict

from peachjam_search.classifier import QueryLabel
from peachjam_search.documents import MultiLanguageIndexManager
from peachjam_search.engine import SearchEngine
from peachjam_search.forms import SearchForm
from peachjam_search.profiles import SearchProfileSet
from peachjam_search.search_pipeline import QueryAnalysis, SearchPlanner, SearchQuery
from peachjam_search.serializers import SearchHit


class Command(BaseCommand):
    help = "Run one SearchEngine query and emit rich JSON for relevance review."

    source_fields = [
        *SearchQuery.default_source["includes"],
        "summary",
        "case_name",
        "case_number",
        "mnc",
        "work_frbr_uri",
        "frbr_uri_country",
        "frbr_uri_locality",
        "frbr_uri_place",
        "frbr_uri_doctype",
        "frbr_uri_subtype",
        "frbr_uri_actor",
        "frbr_uri_language",
        "principal",
        "commenced",
        "repealed",
    ]

    def add_arguments(self, parser):
        parser.add_argument("query", help="The ordinary search query to run.")
        parser.add_argument(
            "--mode", choices=["text", "semantic", "hybrid"], default="text"
        )
        parser.add_argument("--page", type=int, default=1)
        parser.add_argument("--page-size", type=int, default=20)
        parser.add_argument(
            "--ordering", choices=["-score", "date", "-date"], default="-score"
        )
        parser.add_argument(
            "--param",
            action="append",
            default=[],
            metavar="KEY=VALUE",
            help="Additional SearchForm query parameter; repeat for multiple values.",
        )
        parser.add_argument(
            "--index-prefix",
            action="append",
            default=[],
            metavar="PREFIX",
            help="Search this index prefix and its language indexes; repeatable.",
        )
        parser.add_argument(
            "--site-url",
            help="Optional public site URL used to generate absolute result URLs.",
        )
        parser.add_argument("--profile", help="Path to a SearchProfileSet JSON file.")
        parser.add_argument(
            "--intent",
            choices=[label.value for label in QueryLabel],
            help="Force the query intent instead of running the classifier.",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            help="Include Elasticsearch score explanations for returned hits.",
        )
        parser.add_argument(
            "--output", type=Path, help="Write JSON to this path instead of stdout."
        )

    def handle(self, *args, **options):
        self.validate_paging(options)
        search_query = self.build_search_query(options)
        profile_set = self.load_profile_set(options.get("profile"))
        engine = SearchEngine(
            search_query,
            planner=SearchPlanner(profile_set=profile_set) if profile_set else None,
        )
        self.apply_intent_override(engine, options.get("intent"))
        self.apply_index_prefixes(engine, options["index_prefix"])

        debug_payload = engine.build_debug_payload()
        response = engine.execute_search()
        payload = self.build_payload(
            engine,
            response,
            debug_payload,
            site_url=options.get("site_url"),
        )
        output = json.dumps(payload, indent=2, ensure_ascii=False, default=str)

        output_path = options.get("output")
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output + "\n", encoding="utf-8")
            self.stdout.write(f"Wrote {output_path}")
        else:
            self.stdout.write(output)

    def validate_paging(self, options: dict[str, Any]) -> None:
        for name in ("page", "page_size"):
            if options[name] < 1:
                raise CommandError(f"--{name.replace('_', '-')} must be at least 1.")

    def build_search_query(self, options: dict[str, Any]) -> SearchQuery:
        params = QueryDict("", mutable=True)
        params["search"] = options["query"]
        params["ordering"] = options["ordering"]
        reserved_params = {"search", "page", "mode", "ordering"}
        for raw_param in options["param"]:
            if "=" not in raw_param:
                raise CommandError(
                    f"Invalid --param {raw_param!r}; expected KEY=VALUE."
                )
            key, value = raw_param.split("=", 1)
            if not key:
                raise CommandError(
                    f"Invalid --param {raw_param!r}; key cannot be empty."
                )
            if key in reserved_params:
                raise CommandError(
                    f"Use the dedicated option for --param {key}=... instead."
                )
            params.appendlist(key, value)

        form = SearchForm(params)
        if not form.is_valid():
            raise CommandError(form.errors.as_json())

        return replace(
            form.build_search_query(mode=options["mode"]),
            page=options["page"],
            page_size=options["page_size"],
            explain=options["explain"],
            source={"includes": self.source_fields},
        )

    def load_profile_set(self, profile_path: str | None) -> SearchProfileSet | None:
        if not profile_path:
            return None
        try:
            return SearchProfileSet.from_json_path(profile_path)
        except OSError as e:
            raise CommandError(
                f"Could not read profile file {profile_path}: {e}"
            ) from e
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            raise CommandError(f"Invalid profile file {profile_path}: {e}") from e

    def apply_intent_override(self, engine: SearchEngine, intent: str | None) -> None:
        if intent:
            engine.analysis = QueryAnalysis(
                raw_query=engine.search_query.query or "",
                clean_query=engine.search_query.query or "",
                intent=intent,
                confidence=1.0,
            )

    def apply_index_prefixes(self, engine: SearchEngine, prefixes: list[str]) -> None:
        if not prefixes:
            return

        names = []
        for prefix in prefixes:
            prefix = prefix.strip()
            if not prefix:
                raise CommandError("--index-prefix cannot be empty.")
            names.append(prefix)
            names.extend(
                f"{prefix}_{language}"
                for language in MultiLanguageIndexManager.ANALYZERS
            )
        engine.compiler.index = names

    def build_payload(
        self,
        engine: SearchEngine,
        response: Any,
        debug_payload: dict[str, Any],
        site_url: str | None,
    ) -> dict[str, Any]:
        hits = SearchHit.from_es_hits(engine, response.hits)
        return {
            "inputs": debug_payload["inputs"],
            "indexes": self.jsonable(debug_payload["index"]),
            "analysis": debug_payload["analysis"],
            "plan": debug_payload["plan"],
            "compiled_query": debug_payload["redacted_query"],
            "total_hits": self.total_hits(response),
            "returned_hits": len(hits),
            "facets": self.facets(response),
            "results": [self.serialize_hit(hit, site_url) for hit in hits],
        }

    def serialize_hit(self, hit: SearchHit, site_url: str | None) -> dict[str, Any]:
        expression_frbr_uri = hit.expression_frbr_uri
        source = self.jsonable(hit.es_hit.to_dict())
        result = {
            "position": hit.position,
            "document_id": hit.id,
            "index": hit.index,
            "score": hit.score,
            "best_match": hit.best_match,
            "expression_frbr_uri": expression_frbr_uri,
            "work_frbr_uri": source.get("work_frbr_uri")
            or FrbrUri.parse(expression_frbr_uri).work_uri(),
            "url": self.build_result_url(site_url, expression_frbr_uri),
            "source": source,
            "highlights": self.jsonable(hit.highlight),
            "page_matches": self.jsonable(hit.pages),
            "provision_matches": self.jsonable(hit.provisions),
        }
        if hasattr(hit.meta, "explanation"):
            result["explanation"] = self.jsonable(hit.meta.explanation)
        return result

    @staticmethod
    def build_result_url(site_url: str | None, expression_frbr_uri: str) -> str:
        if not site_url:
            return expression_frbr_uri
        return urljoin(site_url.rstrip("/") + "/", expression_frbr_uri.lstrip("/"))

    @staticmethod
    def total_hits(response: Any) -> int | None:
        total = getattr(response.hits, "total", None)
        if total is None:
            return None
        return total.value if hasattr(total, "value") else total

    def facets(self, response: Any) -> dict[str, Any]:
        aggregations = getattr(response, "aggregations", None)
        return self.jsonable(aggregations) if aggregations else {}

    @classmethod
    def jsonable(cls, value: Any) -> Any:
        if hasattr(value, "to_dict") and not isinstance(value, dict):
            value = value.to_dict()
        if isinstance(value, dict):
            return {key: cls.jsonable(child) for key, child in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.jsonable(child) for child in value]
        return value
