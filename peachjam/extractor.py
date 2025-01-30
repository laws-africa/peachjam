import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.files import File
from django.db.models.functions import Lower
from languages_plus.models import Language

from peachjam.models import CaseNumber, Court, Judge, Judgment, SourceFile, pj_settings
from peachjam.storage import clean_filename

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

    def extract_judgment_from_file(self, jurisdiction, file):
        details = self.extract_judgment_details(jurisdiction, file)

        if details.get("language"):
            language = (
                Language.objects.filter(iso_639_3=details["language"].lower()).first()
                or pj_settings().default_document_language
                or Language.objects.get(pk="en")
            )
        else:
            raise ExtractorError("No language detected")

        if details.get("court"):
            try:
                court = Court.objects.get(name=details["court"])
            except Court.DoesNotExist:
                raise ExtractorError(f"Could not find court: {details['court']}")
        else:
            raise ExtractorError("No court detected")

        if details.get("date"):
            try:
                date = datetime.strptime(details["date"], "%Y-%m-%d")
            except ValueError:
                raise ExtractorError(f"Invalid date: {details['date']}")
        else:
            raise ExtractorError("No date detected")

        log.info("Creating new judgment")
        doc = Judgment()
        doc.jurisdiction = jurisdiction
        doc.language = language
        doc.court = court
        doc.date = date
        doc.case_name = details.get("case_name", "")

        if details.get("hearing_date"):
            try:
                doc.hearing_date = datetime.strptime(
                    details["hearing_date"], "%Y-%m-%d"
                )
            except ValueError:
                pass

        doc.save()

        if details.get("judges"):
            judges = Judge.objects.annotate(name_lower=Lower("name")).filter(
                name_lower__in=[s.lower() for s in details["judges"]]
            )
            doc.judges.set(judges)

        # attach source file
        file.seek(0)
        SourceFile(
            document=doc,
            file=File(file, name=clean_filename(file.name)),
            filename=file.name,
            mimetype=file.content_type,
        ).save()

        if doc.extract_content_from_source_file():
            doc.save()

        if doc.extract_citations():
            doc.save()

        # case numbers
        for case_number in details.get("case_numbers") or []:
            # TODO: matter type
            try:
                number = int(case_number["number"])
            except ValueError:
                number = None

            try:
                year = int(case_number["year"])
            except ValueError:
                year = None

            CaseNumber.objects.create(
                document=doc,
                number=number,
                year=year,
                string_override=case_number["case_number_string"],
            )

        return doc
