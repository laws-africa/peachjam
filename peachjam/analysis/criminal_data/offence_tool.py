import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from peachjam.models import JudgmentOffence, Offence

from .base import BaseExtractor
from .search_offences import search_offences

log = logging.getLogger(__name__)


class MatchedOffence(BaseModel):
    extracted_offence: str
    offence_id: Optional[int]
    basis: str


class MatchOffenceResult(BaseModel):
    mappings: List[MatchedOffence] = Field(default_factory=list)


SEARCH_OFFENCES_TOOL = {
    "type": "function",
    "name": "search_offences",
    "description": "Search the offences ontology and return top candidate offences.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


class OffenceToolMatcher(BaseExtractor):
    def system_prompt(self) -> str:
        return (
            "You map offences mentioned in a judgment to a strict offence ontology.\n"
            "You MUST use the tool search_offences(query, k) to retrieve candidate offences.\n"
            "You MUST only return JSON that matches the schema."
        )

    def tools(self):
        return [SEARCH_OFFENCES_TOOL]

    def tool_handlers(self):
        return {"search_offences": search_offences}

    def build_prompt(self) -> str:
        judgment_text = self.judgment.get_content_as_text()
        return f"""
            <ROLE>
            You are a legal charge extraction and ontology mapping engine.
            </ROLE>

            <GOAL>
            Return ONLY the offence(s) that are the charges in this matter (the case against the accused/appellant),
            and map each to an offence_id using search_offences().
            </GOAL>

            <IMPORTANT DEFINITIONS>
            CASE OFFENCE = an offence that the accused/appellant was:
            - charged with, OR
            - convicted of, OR
            - sentenced for, OR
            - acquitted/discharged of, OR
            - explicitly appealing against.

            INCIDENTAL OFFENCE MENTION = any mention that is not a case offence, including:
            - generic phrases like "elements of an offence", "scene of crime"
            - offences mentioned as examples, hypotheticals, background law
            - statutory explanations unless clearly tied to the accused’s charge
            </IMPORTANT DEFINITIONS>

            <INSTRUCTIONS>
            1) Identify the accused/appellant and procedural posture (trial or appeal).
            2) Extract only CASE OFFENCES.
               - Prefer the opening summary and sentencing language.
               - If this is an appeal, extract the offence for which the appellant was convicted/sentenced.
            3) For each CASE OFFENCE:
               a) extracted_offence must be a clean natural-language label (no statute numbers).
               b) basis must be a SHORT quote (max 25 words) copied directly from the judgment text
                  showing the charge/conviction/sentence.
               c) Call search_offences(query, k=20) using the clean label.
               d) Choose the best offence_id from returned candidates.
               e) If no candidate clearly matches, offence_id must be null.
            4) Return JSON only, exactly in this format:

            {{
              "mappings": [
                {{
                  "extracted_offence": "string",
                  "offence_id": 123,
                  "basis": "short supporting quote from the judgment"
                }}
              ]
            }}
            </INSTRUCTIONS>

            <STRICT RULES>
            - DO NOT return incidental or background offences.
            - DO NOT return procedural phrases.
            - Only use offence_id values returned by search_offences.
            - basis must be copied text from the judgment (no paraphrasing).
            - Output JSON only. No commentary.
            </STRICT_RULES>

            <JUDGMENT_TEXT>
            {judgment_text}
            </JUDGMENT_TEXT>
            """.strip()

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

        return created_objs

    def run(self):
        response = self._run_tool_loop(self.build_prompt())
        parsed = self.client.responses.parse(
            model=self.model,
            instructions=self.system_prompt(),
            previous_response_id=response.id,
            input="Return ONLY the final JSON matching the output schema.",
            text_format=self.get_response_format(),
        ).output_parsed

        return self.save(parsed)

    def _run_tool_loop(self, prompt: str):
        response = self.client.responses.create(
            model=self.model,
            instructions=self.system_prompt(),
            input=prompt,
            tools=self.tools(),
        )

        handlers = self.tool_handlers()

        while True:
            calls = [
                item for item in (response.output or []) if item.type == "function_call"
            ]

            # No more function calls => stop. Return the response object (not just text)
            if not calls:
                return response

            outputs = []
            for call in calls:
                name = call.name
                args = call.arguments
                if isinstance(args, str):
                    args = json.loads(args)

                print(args)

                result = handlers[name](**args)

                print(result)

                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            response = self.client.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
            )
