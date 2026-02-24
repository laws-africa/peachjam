import logging

from peachjam.models import JudgmentOffence, Sentence

from .base import BaseExtractor
from .types import SentenceExtractionResult

log = logging.getLogger(__name__)


class SentenceExtractor(BaseExtractor):
    def build_prompt(self) -> str:
        judgment_text = self.judgment.get_content_as_text()
        offences = JudgmentOffence.objects.filter(judgment=self.judgment)

        if offences.exists():
            offences_block = "\n".join(
                [f"- ID: {o.id} | TITLE: {o.offence.title}" for o in offences]
            )
        else:
            offences_block = "No structured offences available."

        return f"""
            You are a legal sentencing extraction engine.

            TASK:
            Extract structured sentencing information from the JUDGMENT_TEXT.

            If OFFENCE_OPTIONS are provided:
            - Link each sentence to the correct OFFENCE ID.
            - If a sentence clearly applies to an offence, use its ID.
            - If unclear or general sentence, use null.

            STRICT RULES:
            1. Only extract sentences explicitly imposed by the court.
            2. Convert all imprisonment/probation durations to MONTHS.
            3. If imprisonment is stated in years, multiply by 12.
            4. If fine amount is stated, extract numeric value only.
            5. If suspended (fully or partially), set suspended=true.
            6. If mandatory minimum is mentioned, set mandatory_minimum=true.
            7. Do NOT invent data.
            8. Return valid JSON only.

            Allowed sentence_type values:
            - imprisonment
            - fine
            - probation

            OUTPUT FORMAT:
            {{
              "sentences": [
                {{
                  "offence_id": <integer or null>,
                  "sentence_type": "imprisonment|fine|probation",
                  "duration_months": <integer or null>,
                  "fine_amount": <integer or null>,
                  "mandatory_minimum": <true|false|null>,
                  "suspended": <true|false>
                }}
              ]
            }}

            OFFENCE_OPTIONS:
            {offences_block}

            JUDGMENT_TEXT:
            \"\"\"
            {judgment_text}
            \"\"\"
            """

    def get_response_format(self):
        return SentenceExtractionResult

    def save(self, parsed: SentenceExtractionResult):
        created_objects = []

        for s in parsed.sentences:
            judgment_offence = None

            if s.offence_id:
                judgment_offence = JudgmentOffence.objects.filter(
                    id=s.offence_id,
                    judgment=self.judgment,
                ).first()

            sentence = Sentence.objects.create(
                judgment=self.judgment,
                offence=judgment_offence,
                sentence_type=s.sentence_type,
                duration_months=s.duration_months,
                fine_amount=s.fine_amount,
                mandatory_minimum=s.mandatory_minimum,
                suspended=s.suspended or False,
            )

            created_objects.append(sentence)
            log.info(
                f"Created Sentence (type={sentence.sentence_type})"
                f"for judgment {self.judgment.id}"
            )

        return created_objects
