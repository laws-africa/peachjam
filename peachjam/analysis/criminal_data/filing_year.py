import logging

from pydantic import BaseModel

from .base import BaseExtractor

log = logging.getLogger(__name__)


class FilingYearResult(BaseModel):
    filing_year: int


class FilingYearExtractor(BaseExtractor):
    def system_prompt(self) -> str:
        return """
           You are a legal metadata extraction assistant.

            Extract the filing year of the case from JUDGMENT_TEXT.

            Rules:
            - Only use years explicitly present in the text.
            - Do NOT infer based on judgment date.
            - Do NOT guess.
            - If not found, return null.
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
        return FilingYearResult

    def save(self, parsed: FilingYearResult):
        filing_year = parsed.filing_year
        log.info(
            f"Filing year identified: {filing_year} for judgment {self.judgment.id}"
        )
        self.judgment.filing_year = filing_year
        self.judgment.save(update_fields=["filing_year"])
        return filing_year
