import json
import logging
from dataclasses import dataclass
from typing import List

from django.conf import settings
from openai import OpenAI

from peachjam.models import JudgmentOffence, Offence

log = logging.getLogger(__name__)


@dataclass
class ExtractedOffence:
    name: str


@dataclass
class OffenceOption:
    id: int
    title: str
    provision_eid: str
    description: str


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
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.judgment = judgment

    def _offence_mention_prompt(self, judgment_text: str) -> str:
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
            8. Output valid JSON only.

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

    def extract_offence_mentions(self, judgment_text: str) -> List[str]:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You extract structured criminal offence data from court judgments.",
                },
                {
                    "role": "user",
                    "content": self._offence_mention_prompt(judgment_text),
                },
            ],
        )

        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
            offences = parsed.get("mentioned_offences", [])
        except json.JSONDecodeError:
            return []

        return list({o.strip().lower() for o in offences if o.strip()})

    def extract_and_save_offence_mentions(self):
        offence_mentions = self.extract_offence_mentions()
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
        if not hasattr(self.judgment.metadata_json, "extracted_offences"):
            log.error(f"judgment {self.judgment} does not have extracted_offences")

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

        prompt = self._build_prompt(
            self.judgment.metadata_json["extracted_offences"],
            offence_options,
        )

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You perform strict ontology classification.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
            mappings = parsed.get("mappings", [])
        except json.JSONDecodeError:
            return []

        offence_ids = [m["offence_id"] for m in mappings if m.get("offence_id")]

        return list(Offence.objects.filter(id__in=offence_ids))

    def match_and_create_judgment_offences(self):
        offences = self.match_offences()
        log.info(f"Matched {len(offences)} for {self.judgment}")
        for offence in offences:
            o, _ = JudgmentOffence.objects.get_or_create(
                judgment=self.judgment, offence=offence
            )
            log.info(o)
