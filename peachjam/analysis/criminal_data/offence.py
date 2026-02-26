import json
import logging

from peachjam.models import JudgmentOffence, Offence

from .base import BaseExtractor
from .types import MatchOffenceResult, MentionedOffences

log = logging.getLogger(__name__)


class OffenceMentionExtractor(BaseExtractor):
    def system_prompt(self) -> str:
        return """
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
            7. If no offences are mentioned, return an empty list.
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
        return MentionedOffences

    def save(self, parsed: MentionedOffences):
        offences = list(
            {o.strip().lower() for o in parsed.mentioned_offences if o.strip()}
        )
        log.info(f"Offences mentioned in {self.judgment.id}: {offences}")

        metadata = self.judgment.metadata_json or {}
        metadata["extracted_offences"] = offences
        self.judgment.metadata_json = metadata
        self.judgment.save(update_fields=["metadata_json"])
        return offences


class OffenceMatcher(BaseExtractor):
    def system_prompt(self) -> str:
        return """
                You are a legal ontology mapping engine.
                You perform strict ontology classification.

                TASK:
                Map each EXTRACTED_OFFENCE to the correct offence
                from OFFENCE_OPTIONS.

                STRICT RULES:
                1. You must only return IDs from OFFENCE_OPTIONS.
                2. Do NOT invent new offences.
                3. If no suitable match exists, return null for that entry.
                4. Use semantic meaning, not exact string matching.
                5. Return valid JSON only. No commentary.
                """

    def build_prompt(self) -> str:
        extracted_offences = self.judgment.metadata_json.get("extracted_offences", [])
        offences = Offence.objects.all()

        offences_block = "\n".join(
            [
                f"- ID: {o.id}\n"
                f"  TITLE: {o.title}\n"
                f"  PROVISION_EID: {o.provision_eid}\n"
                f"  DESCRIPTION: {o.description[:500] if o.description else 'N/A'}"
                for o in offences
            ]
        )

        return f"""
                EXTRACTED_OFFENCES:
                {json.dumps(extracted_offences, indent=2)}

                OFFENCE_OPTIONS:
                {offences_block}
                """

    def get_response_format(self):
        return MatchOffenceResult

    def save(self, parsed: MatchOffenceResult):
        offence_ids = [m.offence_id for m in parsed.mappings if m.offence_id]
        offences = list(Offence.objects.filter(id__in=offence_ids))
        log.info(f"Mapped {len(offences)} offences for judgment {self.judgment.id}")

        created_objs = []
        for offence in offences:
            obj, _ = JudgmentOffence.objects.get_or_create(
                judgment=self.judgment,
                offence=offence,
            )
            created_objs.append(obj)
            log.info(
                f"Created JudgmentOffence {obj.id} for offence {offence} for judgment {self.judgment.id}"
            )

        return created_objs
