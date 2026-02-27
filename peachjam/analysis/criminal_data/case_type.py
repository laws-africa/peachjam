import logging

from pydantic import BaseModel

from peachjam.models import Judgment

from .base import BaseExtractor

log = logging.getLogger(__name__)


class CaseTypeResult(BaseModel):
    case_type: Judgment.CaseType


class CaseTypeExtractor(BaseExtractor):
    def system_prompt(self) -> str:
        return """
            You are a legal case classification engine.

            TASK:
            Determine whether the judgment is:

            - criminal
            - civil
            - unknown

            Definitions:

            CRIMINAL:
            - Prosecution by the State
            - Accused/defendant charged with offences
            - Conviction, acquittal, sentence
            - Penal Code or criminal statutes referenced

            CIVIL:
            - Disputes between private parties
            - Contracts, torts, land, family, commercial disputes
            - Damages, injunctions, declarations

            UNKNOWN:
            - If the nature cannot clearly be determined

            STRICT RULES:
            1. Base decision only on JUDGMENT_TEXT.
            2. Do NOT guess.
            """

    def build_prompt(self) -> str:
        judgment_text = self.judgment.get_content_as_text()
        return f"""
            JUDGMENT_TEXT:
            \"\"\"
            {judgment_text}
            \"\"\"
            """

    def get_response_format(self):
        return CaseTypeResult

    def save(self, parsed: CaseTypeResult):
        case_type = parsed.case_type.lower()
        log.info(f"Case type identified: {case_type} for judgment {self.judgment.id}")
        self.judgment.case_type = case_type
        self.judgment.save(update_fields=["case_type"])
        return case_type
