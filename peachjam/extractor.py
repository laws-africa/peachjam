import logging
from datetime import datetime

import requests
from django.conf import settings
from django.db.models.functions import Lower
from languages_plus.models import Language

from peachjam.models import CaseNumber, Court, Judge, MatterType, pj_settings

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
            details["judges"] = list(
                Judge.objects.annotate(name_lower=Lower("name")).filter(
                    name_lower__in=[s.lower() for s in details["judges"]]
                )
            )

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
