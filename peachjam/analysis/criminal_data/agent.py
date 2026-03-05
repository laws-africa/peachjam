import logging
import re
from typing import Any, Dict, List, Literal, Optional, Sequence, Union

from agents import Agent, Runner, function_tool
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from pydantic import BaseModel, Field, conint

from peachjam.models import Offence, Sentence

log = logging.getLogger(__name__)

KeywordInput = Union[str, Sequence[str]]
_SPLIT = re.compile(r"[,\n;|]+")


@function_tool
def search_offences(
    keywords: KeywordInput,
    *,
    limit: int = 20,
    min_rank: Optional[float] = None,
    config: str = "english",
) -> List[Dict[str, Any]]:
    """
    Perform a full-text search against the offence database using one or
    more offence-related keywords or phrases extracted from a judgment.

    Purpose
    -------
    This tool is used to match offence mentions found in a judgment
    against canonical offences stored in the database.

    It supports providing MULTIPLE keywords or alternative phrases in
    order to cast a broader search net (for example, synonyms, shortened
    forms, or variations of the offence name).

    When to Use
    -----------
    - Call this tool for each distinct offence mention identified in the judgment.
    - If the offence wording is ambiguous or long, provide multiple concise
      keyword variants to improve recall.
    - Always attempt a database search before concluding that no match exists.
    - Never invent offence IDs without calling this tool.

    Parameters
    ----------
    keywords : str
        A string containing one or more keywords or short phrases describing
        the offence. Multiple alternatives may be included, separated by commas.

        Examples:
            "robbery with violence"
            "defilement, sexual assault"
            "obtaining by false pretences, fraud"

        Guidelines:
        - Keep each keyword concise (avoid full sentences).
        - Include statutory section numbers if present (e.g. "296(2)").
        - Include synonyms or simplified versions if helpful.
        - Do NOT include procedural phrases like "contrary to" or
          "as read with".

    Returns
    -------
    A ranked list (maximum 20) of candidate offences:

        [
            {
                "id": str,                     # canonical offence ID
                "title": str,                  # official offence title
                "description_snippet": str     # short excerpt from description
            },
            ...
        ]

    Result Interpretation
    ---------------------
    - Results are ranked by PostgreSQL full-text search relevance.
    - Higher-ranked results are more likely to match the intended offence.
    - Prefer candidates that:
        * closely match the offence wording
        * align with any mentioned statutory section
        * align with contextual clues in the judgment

    Matching Strategy (Agent Guidance)
    -----------------------------------
    - If unsure, try multiple variations of the offence name
      (e.g., full name + shortened name).
    - If the first search does not return a strong match,
      refine the keywords and call the tool again.
    - If multiple counts refer to the same offence, the same
      offence ID may be reused.
    - If no reasonable candidate appears, treat the offence
      as unmatched and assign low confidence.

    Constraints
    -----------
    - Never fabricate offence IDs.
    - Always base selections strictly on returned results.
    - If no keywords are provided, the tool returns an empty list.
    """
    log.info(f"search for offences keywords: {keywords}")

    if isinstance(keywords, str):
        terms = [t.strip() for t in _SPLIT.split(keywords)]
    else:
        terms = [str(t).strip() for t in (keywords or [])]
        terms = [p.strip() for t in terms for p in _SPLIT.split(t)]
    terms = list(dict.fromkeys([t for t in terms if t]))  # dedupe, preserve order
    if not terms:
        return []

    vector = SearchVector("title", weight="A", config=config) + SearchVector(
        "description", weight="B", config=config
    )

    ts_query = None
    for t in terms:
        q = SearchQuery(t, search_type="plain", config=config)
        ts_query = q if ts_query is None else (ts_query | q)

    rank = SearchRank(vector, ts_query)
    qs = Offence.objects.annotate(rank=rank).order_by("-rank")
    if min_rank is not None:
        qs = qs.filter(rank__gte=min_rank)

    results: List[Dict[str, Any]] = []
    for o in qs[:limit]:
        desc = (o.description or "").strip()
        results.append(
            {
                "id": o.id,
                "title": o.title,
                "description_snippet": (desc[:220] + "…") if len(desc) > 220 else desc,
            }
        )
    log.info(f"results:{results}")
    return results


PROMPT = """
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
- Choose the best matching offence_id from the results.
- Never invent an offence_id.
- If no clear match exists, offence_id = null.

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

OUTPUT (shape only):
{
  "offences": [
    {
      "offence_id": 123,
      "extracted_offence": "robbery with violence",
      "basis": "convicted of robbery with violence contrary to section 296(2)",
      "sentences": [
        {"sentence_type":"imprisonment",
        "duration_months":120,"suspended":false,"mandatory_minimum":null,"basis":"sentenced to ten years imprisonment"}
      ]
    }
  ]
}
"""


class SentenceOutput(BaseModel):
    sentence_type: Sentence.SentenceType
    duration_months: Optional[int] = None
    fine_amount: Optional[int] = None
    suspended: bool = False
    mandatory_minimum: Optional[bool] = None
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
