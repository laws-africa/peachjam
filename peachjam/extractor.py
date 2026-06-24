import logging
from collections import defaultdict
from datetime import datetime

import requests
from django.conf import settings
from django.db.models.functions import Lower
from languages_plus.models import Language

from peachjam.analysis.judges import judge_identity_service
from peachjam.models import (
    CaseNumber,
    Court,
    Judge,
    JudgePerson,
    MatterType,
    pj_settings,
)

log = logging.getLogger(__name__)


class ExtractorError(Exception):
    pass


class ExtractorService:
    def __init__(self):
        self.api_token = settings.PEACHJAM["LAWSAFRICA_API_KEY"]
        self.api_url = settings.PEACHJAM["EXTRACTOR_API"]

    def enabled(self):
        return self.api_token and self.api_url

    def extract_judgment_details(self, jurisdiction, file):
        if not self.enabled():
            raise ExtractorError("Extractor service not configured")

        data = {
            "country": jurisdiction.pk,
            "court_names": [c.name for c in Court.objects.all()],
            "matter_types": [m.name for m in MatterType.objects.all()],
        }
        headers = self.get_headers()
        resp = requests.post(
            self.api_url + "extract/judgment",
            files={"file": file},
            data=data,
            headers=headers,
        )
        if resp.status_code != 200:
            raise ExtractorError(
                f"Error calling extractor service: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        log.info(f"Extracted details: {data}")
        return data["extracted"]

    def get_headers(self):
        return {"Authorization": "Token " + self.api_token}

    def process_judgment_details(self, details):
        if details.get("language"):
            details["language"] = (
                Language.objects.filter(iso_639_3=details["language"].lower()).first()
                or pj_settings().default_document_language
                or Language.objects.get(pk="en")
            )

        if details.get("court"):
            try:
                details["court"] = Court.objects.get(name=details["court"])
            except Court.DoesNotExist:
                details["court"] = None

        for field in ["date", "hearing_date"]:
            if details.get(field):
                try:
                    details[field] = datetime.strptime(details[field], "%Y-%m-%d")
                except ValueError:
                    details[field] = None

        if details.get("judges"):
            raw_judges = [
                judge_name.strip()
                for judge_name in details["judges"]
                if (judge_name or "").strip()
            ]
            if not JudgePerson.canonical_identity_enabled():
                details["judges"] = list(
                    Judge.objects.annotate(name_lower=Lower("name")).filter(
                        name_lower__in=[judge_name.lower() for judge_name in raw_judges]
                    )
                )
            else:
                details["extracted_judges"] = raw_judges

                exact_legacy_judges = {
                    judge.name_lower: judge
                    for judge in Judge.objects.annotate(
                        name_lower=Lower("name")
                    ).filter(
                        name_lower__in=[judge_name.lower() for judge_name in raw_judges]
                    )
                }

                alias_matches = defaultdict(list)
                for judge_alias in judge_identity_service.get_matching_judge_aliases(
                    raw_judges
                ):
                    alias_matches[judge_alias.normalized_name].append(judge_alias)

                fallback_legacy_judges = {
                    judge.name: judge
                    for judge in Judge.objects.filter(
                        name__in={
                            aliases[0].name
                            for aliases in alias_matches.values()
                            if len(aliases) == 1
                        }
                    )
                }

                bench_rows = []
                details["judges"] = []

                for raw_name in raw_judges:
                    normalized_name = judge_identity_service.normalize_judge_name(
                        raw_name
                    )
                    matching_aliases = alias_matches.get(normalized_name, [])
                    matched_alias = (
                        matching_aliases[0] if len(matching_aliases) == 1 else None
                    )
                    judge_person = (
                        matched_alias.judge_person
                        if matched_alias is not None
                        else None
                    )
                    judge_person_suggestion = ""

                    if judge_person is None:
                        resolution = judge_identity_service.resolve_judge_person(
                            [raw_name],
                            dry_run=True,
                        )
                        judge_person_suggestion = resolution["canonical_name"]
                        if resolution["judge_person"].pk:
                            judge_person = resolution["judge_person"]

                    legacy_judge = exact_legacy_judges.get(raw_name.lower())
                    if legacy_judge is None and matched_alias is not None:
                        legacy_judge = fallback_legacy_judges.get(matched_alias.name)

                    if legacy_judge is not None:
                        details["judges"].append(legacy_judge)

                    bench_rows.append(
                        {
                            "judge": legacy_judge,
                            "extracted_name": raw_name,
                            "matched_alias": matched_alias,
                            "judge_person": judge_person,
                            "judge_person_suggestion": judge_person_suggestion,
                        }
                    )

                details["bench_rows"] = bench_rows

        # case numbers
        if details.get("case_numbers"):
            case_numbers = []
            for case_number in details["case_numbers"]:
                matter_type = None
                if case_number.get("matter_type"):
                    matter_type = MatterType.objects.filter(
                        name=case_number["matter_type"]
                    ).first()

                try:
                    number = int(case_number["number"])
                except (TypeError, ValueError):
                    number = None

                try:
                    year = int(case_number["year"])
                except (TypeError, ValueError):
                    year = None

                case_numbers.append(
                    CaseNumber(
                        matter_type=matter_type,
                        number=number,
                        year=year,
                        string_override=case_number["case_number_string"],
                    )
                )
            details["case_numbers"] = case_numbers
