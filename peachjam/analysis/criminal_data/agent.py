import logging
import re
from typing import Any, Dict, List, Literal, Optional

from agents import Agent, Runner, function_tool
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import close_old_connections, connection
from pydantic import BaseModel, Field, conint

from peachjam.models import Offence, Sentence

log = logging.getLogger(__name__)


@function_tool
def search_offences(search_terms: str) -> List[Dict[str, Any]]:
    """
    Search the offence database for offences matching one or more offence-related terms.

    Purpose
    -------
    This tool maps offence mentions found in a judgment to canonical offences
    stored in the database.

    Input
    -----
    search_terms : str

        A single string containing one or more offence search terms.

        If multiple terms are needed, separate them with commas.

        Examples:
            "robbery with violence"
            "robbery with violence, robbery, theft"
            "criminal trespass, trespass, unlawful entry"

    Agent Guidance
    --------------
    - Always call this tool before assigning an offence_id.
    - Provide 3–5 concise keyword variants when possible.
    - Never invent offence IDs.

    Returns
    -------
    A ranked list of offence candidates:

        [
            {
                "id": str,                     # canonical offence ID
                "title": str,                  # official offence title
                "description_snippet": str     # short excerpt from description
            },
            ...
        ]

    Notes
    -----
    - Results are ranked using PostgreSQL full-text search over the offence
      title and description.
    - Sorting is deterministic: rank DESC, title ASC, id ASC.
    """

    close_old_connections()
    try:
        log.info("search for offences terms: %s", search_terms)

        _SPLIT = re.compile(r"[,\n;|]+")

        terms = [t.strip() for t in _SPLIT.split(search_terms or "")]
        terms = list(dict.fromkeys([t for t in terms if t]))
        if not terms:
            return []

        config = "english"
        limit = 5
        min_rank = 0.08

        vector = SearchVector("title", weight="A", config=config) + SearchVector(
            "description", weight="B", config=config
        )

        ts_query = None
        for term in terms:
            q = SearchQuery(term, search_type="plain", config=config)
            ts_query = q if ts_query is None else (ts_query | q)

        rank = SearchRank(vector, ts_query)

        qs = (
            Offence.objects.annotate(rank=rank)
            .filter(rank__gte=min_rank)
            .order_by("-rank", "title", "id")  # stable ordering
        )

        results: List[Dict[str, Any]] = []

        for offence in qs[:limit]:
            results.append(
                {
                    "id": offence.id,
                    "title": offence.title,
                    "description": (offence.description or "").strip(),
                }
            )

        log.info("offence search results: %s", results)

        return results

    finally:
        connection.close()


PROMPT = """
You are a legal information extraction system that is extracting structured data on case offences and sentencing from
the text of a court judgment.

# Task

Your task is to identify the specific offences that the accused/appellant was charged with, convicted of,
acquitted of, or sentenced for, and to extract any sentences imposed on the accused/appellant, ensuring that each
sentence is correctly matched to the relevant offence.

# Instructions

## Extracting offences

Extract only CASE OFFENCES, which are offences directly related to the accused/appellant's charges, convictions,
acquittals, or sentences.

Do not extract INCIDENTAL mentions of offences that are not directly related to the accused/appellant's case.
These include general legal discussions, examples, hypotheticals, or offences committed by other individuals that
are not part of the charges against the accused/appellant.

### Use the search_offences tool for mapping offences to IDs

For each extracted offence, you MUST the search_offences tool to find candidate offence IDs from the database. Provide
3–5 concise keyword variants for each offence when calling search_offences. Use the search results solely to map the
already-extracted offence to a database offence. Assign an offence_id only if there is a clear semantic match between
the extracted offence text and the title or description of a candidate offence from search_offences.

If search_offences returns no results, or if none of the results clearly match the extracted offence, set offence_id
to null. Do not invent offence IDs or assign an ID that does not appear in the search results.

## Extracting sentences and matching to offences

If a sentence is present in the text, extract it and associate it to the corresponding offence.

If a sentence is a general one that is not clearly linked to a specific offence, try to attach it to the most clearly
convicted offence(s). If it is still unclear, attach it to the first offence mentioned.

Only extract sentences that are actually imposed on the accused/appellant. Do not extract sentences mentioned in
general discussion or that are not clearly linked to the accused/appellant.

The possible sentence types that can be extracted are:

- imprisonment: Look for phrases like "sentenced to X years/months" or "imprisonment for X".
- fine: Look for phrases like "fined <currency> X" or "fine of X".
- probation: Look for phrases like "placed on probation for X years/months".

Also extract the following information about the sentence, if available. If not available, use null for that field.

- duration_months: the duration (in months) of the sentence. Convert years to months (e.g., 10 years -> 120 months).
- fine_amount: the amount of the fine (if a fine was imposed). Use a number only, without currency symbols.
- suspended: set to True if the sentence is stated as suspended, otherwise False.
- mandatory_minimum: set to True only if the sentence is explicitly stated as the mandatory minimum for the offence.

# Examples

## Example 1

<text>
The appellant was convicted of robbery with violence contrary to section 296(2) and sentenced to ten years imprisonment.
</text>

The search_offences tool is called with the input "robbery with violence, robbery, theft, stealing" and the tool
returns:

<tool-output>
[{
  "id": 123,
  "title": "Robbery with Violence",
  "description": "An offence involving robbery with the use of violence, as defined in section 296
}]
</tool-output>

Since this is a clear semantic match to the extracted offence "robbery with violence", offence_id 123 is used.

The sentence "ten years imprisonment" is extracted and attached to this offence, with:

- sentence_type="imprisonment",
- duration_months=120 (10 years * 12 months)
- fine_amount=null
- suspended=False
- mandatory_minimum=null
"""


PROMPT2 = """
<ROLE>
You extract case offences and sentencing from judgment text and map offences to database IDs.
</ROLE>

<TASK>
Return only:
- offences that are charges/convictions/acquittals/sentences for the accused/appellant (CASE OFFENCES)
- sentences imposed on the accused/appellant, matched to the correct offence
</TASK>

<CASE OFFENCE vs INCIDENTAL>
CASE OFFENCE = offence the accused/appellant was charged with / convicted of / acquitted of / sentenced for / appealing.
INCIDENTAL = examples, hypotheticals, general legal discussion, offences by other persons not part of the charges.

Only extract CASE OFFENCES.

<MANDATORY TOOL USE>
For EACH extracted offence you MUST call search_offences to obtain candidate offence IDs.
- Call search_offences with 3–5 concise keyword variants, comma-separated.
- Use the search results only to map the already-extracted offence to a database offence.
- Assign offence_id only if a candidate is a clear semantic match to the extracted offence text.
- A candidate is a clear match only if its title or description closely matches the extracted offence wording.

<IMPORTANT>
- You are not allowed to invent offence_id
- You are not allowed to output any offence_id unless that exact ID appears in the search_offences results for that
offence.
- If search_offences returns no results, offence_id must be null.
- If search_offences returns results but none clearly match, offence_id must be null.

Example call:
search_offences("robbery with violence, robbery, theft, stealing")

<SENTENCING EXTRACTION (MATCH TO OFFENCE)>
If a sentence is present, attach it to the correct offence.
Extract only sentences imposed on the accused/appellant.

Sentence types:
- imprisonment: "sentenced to X years/months", "imprisonment for X"
- fine: "fined KSh X", "fine of X"
- probation: "placed on probation for X years/months"

Convert years to months (e.g., 10 years -> 120).
Set suspended=True if suspension is stated.
Set mandatory_minimum=True only if explicitly stated as mandatory minimum.

If sentencing is global (not linked to a count/offence):
- attach it to the most clearly convicted offence(s) if possible
- if still unclear, attach to the first offence and use a basis quote that shows ambiguity

<QUOTES>
For every offence, include:
- basis: <= 25 words showing charge/conviction/acquittal/sentence for that offence.
For every sentence, include:
- basis: <= 25 words showing the sentence.

Return structured data only.

<EXAMPLE 1>
TEXT:
"The appellant was convicted of robbery with violence contrary to section 296(2)
and sentenced to ten years imprisonment."
"""


class SentenceOutput(BaseModel):
    sentence_type: Sentence.SentenceType
    duration_months: Optional[int] = Field(
        description="Duration of the sentence in months. Convert years to months (e.g., 10 years -> 120 months)."
    )
    fine_amount: Optional[int] = Field(
        description="Amount of the fine (if a fine was imposed). Use a number only, without currency symbols."
    )
    suspended: bool = Field(
        description="Whether the sentence is suspended or not.",
        default=False,
    )
    mandatory_minimum: Optional[bool] = Field(
        description="Whether the sentence is explicitly stated as the mandatory minimum for the offence.",
        default=None,
    )
    basis: str = Field(description="Short quote (<=25 words) supporting this sentence.")


class OffenceMatch(BaseModel):
    offence_id: Optional[int] = Field(
        description="Offence ID from the database (from search_offences). Null if no clear match."
    )
    extracted_offence: str = Field(
        description="Clean offence label as written/normalized (no statute numbers)."
    )
    basis: str = Field(
        description="Short quote (<=25 words) showing charge/conviction/acquittal/sentence for this offence."
    )
    sentences: List[SentenceOutput] = []


class JudgmentOffenceExtraction(BaseModel):
    offences: List[OffenceMatch] = []


def extract_offences_and_sentences(judgment_text: str) -> JudgmentOffenceExtraction:
    agent = Agent(
        name="Offence + Sentence Extractor",
        instructions=PROMPT,
        tools=[search_offences],
        output_type=JudgmentOffenceExtraction,
    )
    return Runner.run_sync(agent, judgment_text).final_output


CaseTypeLiteral = Literal["criminal", "civil"]


class CaseMetaExtraction(BaseModel):
    case_type: Optional[CaseTypeLiteral] = Field(
        default=None,
        description="Case type for the matter: criminal, civil, or null if unclear.",
    )
    filing_year: Optional[conint(ge=1800, le=2200)] = Field(
        default=None,
        description="Year the case/appeal was filed (4-digit), or null if not stated/unclear.",
    )
    basis: str = Field(
        description="Short quote (<=25 words) supporting case_type and/or filing_year. If neither is found, "
        "explain briefly why (<=25 words)."
    )


CASE_META_PROMPT = """
<ROLE>
You extract filing year and case type from judgment text.
</ROLE>

<TASK>
Return:
- case_type: criminal | civil | null (unknown)
- filing_year: 4-digit year | null
- basis: <=25 words supporting the extracted values (or why unknown)

<CASE TYPE RULES>
- criminal: accused/appellant convicted/acquitted/sentenced; criminal charges; Penal Code; Criminal Appeal;
prosecution/State.
- civil: plaintiff/defendant; contract/tort/property; damages; injunction; constitutional petition is NOT
 automatically civil unless clearly framed as civil.
- If mixed/unclear, return null.

<FILING YEAR RULES>
Extract the filing year ONLY if the text clearly indicates filing/registration year, e.g.:
- "Criminal Appeal No. 12 of 2019"
- "Civil Appeal No. 3 of 2020"
- "filed in 2018"
- "lodged in 2021"
If you only see incident dates (e.g. offence date 14 March 2019) or judgment date without a filing signal,
filing_year = null.

<OUTPUT>
Return structured data only.
"""


def extract_case_type_filing_year(judgment_text: str) -> CaseMetaExtraction:
    agent = Agent(
        name="Case Type + Filing Year Extractor",
        instructions=CASE_META_PROMPT,
        output_type=CaseMetaExtraction,
    )
    return Runner.run_sync(agent, judgment_text).final_output
