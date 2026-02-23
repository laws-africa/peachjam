import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from peachjam.models import JudgmentOffence, Offence

log = logging.getLogger(__name__)


class MentionedOffences(BaseModel):
    mentioned_offences: List[str]


@dataclass
class OffenceOption:
    id: int
    title: str
    provision_eid: str
    description: str


class MatchedOffence(BaseModel):
    extracted_offence: str
    offence_id: Optional[int]


class MatchOffenceResult(BaseModel):
    mappings: list[MatchedOffence] = Field(default_factory=list)


class JudgmentOffenceMentionExtractor:
    """
    This can be done in 2 steps
    Stage 1:
    Extracts offences mentioned in a judgment in natural language.
    Does NOT map to database.
    Stage 2:
    Match extracted offences to those stored in db,
    """

    def __init__(self, judgment):
        self.judgment = judgment

    def _offence_mention_prompt(self) -> str:
        judgment_text = self.judgment.get_content_as_text()
        return f"""
            You are a legal information extraction engine.

            TASK:
            Identify all criminal offences mentioned in the JUDGMENT_TEXT.

            STRICT RULES:
            1. Extract only offences that are clearly mentioned.
            2. Do NOT invent offences.
            3. Use natural language offence names as written or clearly implied.
            4. Normalize similar mentions into a single clean name.
               Example: "robbery contrary to section 296(2)" → "robbery with violence"
            5. Do NOT include statutory numbers in the offence name.
            6. Do NOT include sentencing information.
            7. If none are mentioned, return an empty list.

            OUTPUT FORMAT:
            {{
              "mentioned_offences": [
                "<offence name 1>",
                "<offence name 2>"
              ]
            }}

            JUDGMENT_TEXT:
            \"\"\"
            {judgment_text}
            \"\"\"
            """

    def extract_offence_mentions(self) -> List[str]:
        client = OpenAI()
        response = client.responses.parse(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "system",
                    "content": "You extract structured criminal offence data from court judgments.",
                },
                {
                    "role": "user",
                    "content": self._offence_mention_prompt(),
                },
            ],
            text_format=MentionedOffences,
        )

        offences = response.output_parsed.mentioned_offences
        result = list({o.strip().lower() for o in offences if o.strip()})
        log.info(f"offence extraction results: {result}")
        return result

    def extract_and_save_offence_mentions(self):
        offence_mentions = self.extract_offence_mentions()
        if not self.judgment.metadata_json:
            self.judgment.metadata_json = {}
        self.judgment.metadata_json["extracted_offences"] = offence_mentions
        self.judgment.save()
        return self.judgment

    def match_offences_prompt(
        self,
        extracted_offences: List[str],
        offence_options: List[OffenceOption],
    ) -> str:

        offences_block = "\n".join(
            [
                f"- ID: {o.id}\n"
                f"  TITLE: {o.title}\n"
                f"  PROVISION_EID: {o.provision_eid}\n"
                f"  DESCRIPTION: {o.description[:500] if o.description else 'N/A'}"
                for o in offence_options
            ]
        )

        return f"""
                You are a legal ontology mapping engine.

                TASK:
                Map each EXTRACTED_OFFENCE to the correct offence
                from OFFENCE_OPTIONS.

                STRICT RULES:
                1. You must only return IDs from OFFENCE_OPTIONS.
                2. Do NOT invent new offences.
                3. If no suitable match exists, return null for that entry.
                4. Use semantic meaning, not exact string matching.
                5. Return valid JSON only. No commentary.

                OUTPUT FORMAT:
                {{
                  "mappings": [
                    {{
                      "extracted": "<original extracted string>",
                      "offence_id": <integer or null>
                    }}
                  ]
                }}

                EXTRACTED_OFFENCES:
                {json.dumps(extracted_offences, indent=2)}

                OFFENCE_OPTIONS:
                {offences_block}
                """

    def match_offences(self) -> List[Offence]:
        if "extracted_offences" not in self.judgment.metadata_json:
            log.error(f"judgment {self.judgment} does not have extracted_offences")
            raise

        offence_queryset = Offence.objects.all()

        offence_options = [
            OffenceOption(
                id=o.id,
                title=o.title,
                provision_eid=o.provision_eid,
                description=o.description or "",
            )
            for o in offence_queryset
        ]

        prompt = self.match_offences_prompt(
            self.judgment.metadata_json["extracted_offences"],
            offence_options,
        )

        client = OpenAI()
        response = client.responses.parse(
            model="gpt-5-mini",
            input=[
                {
                    "role": "system",
                    "content": "You perform strict ontology classification.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            text_format=MatchOffenceResult,
        )

        mappings = response.output_parsed.mappings
        offence_ids = [m.offence_id for m in mappings if m.offence_id]
        return list(Offence.objects.filter(id__in=offence_ids))

    def match_and_create_judgment_offences(self):
        offences = self.match_offences()
        log.info(f"Matched {len(offences)} for {self.judgment}")
        for offence in offences:
            o, _ = JudgmentOffence.objects.get_or_create(
                judgment=self.judgment, offence=offence
            )
            log.info(o)
