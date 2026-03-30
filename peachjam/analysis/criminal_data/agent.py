import logging
import re
from typing import Any, Dict, List, Literal, Optional

from agents import Agent, ModelSettings, ReasoningItem, Runner, RunResult, function_tool
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import close_old_connections, connection
from django.db.models import Case, FloatField, Q, Value, When
from openai.types import Reasoning
from pydantic import BaseModel, Field, conint

from peachjam.models import Offence, Outcome, Sentence

log = logging.getLogger(__name__)


def log_agent_reasoning(result: RunResult):
    for item in result.new_items:
        if isinstance(item, ReasoningItem):
            for entry in item.raw_item.summary:
                log.debug("LLM reasoning: %s", entry.text)


def search_offences_tool(search_terms: str) -> List[Dict[str, Any]]:

    _SPLIT = re.compile(r"[,\n;|]+")
    _WS = re.compile(r"\s+")
    _WORDS = re.compile(r"[a-z0-9]+")

    def _normalize_term(term: str) -> str:
        return _WS.sub(" ", (term or "").strip().lower())

    def _term_words(term: str) -> List[str]:
        return _WORDS.findall(_normalize_term(term))

    close_old_connections()
    try:
        log.info("search for offences terms: %s", search_terms)

        terms = [_normalize_term(t) for t in _SPLIT.split(search_terms or "")]
        terms = [t for t in terms if t]
        terms = list(dict.fromkeys(terms))

        if not terms:
            return []

        primary_term = terms[0]
        query_terms = terms[:3]

        config = "english"
        limit = 5
        min_rank = 0.05

        vector = SearchVector("title", weight="A", config=config) + SearchVector(
            "description", weight="C", config=config
        )

        ts_query = None
        for term in query_terms:
            q = SearchQuery(term, search_type="plain", config=config)
            ts_query = q if ts_query is None else (ts_query | q)

        rank = SearchRank(vector, ts_query)

        title_word_score_parts = []
        for word in _term_words(primary_term):
            title_word_score_parts.append(
                Case(
                    When(title__icontains=word, then=Value(1.0)),
                    default=Value(0.0),
                    output_field=FloatField(),
                )
            )

        qs = Offence.objects.annotate(rank=rank)

        if title_word_score_parts:
            title_word_score = title_word_score_parts[0]
            for extra_score in title_word_score_parts[1:]:
                title_word_score = title_word_score + extra_score
            qs = qs.annotate(title_word_score=title_word_score)
        else:
            qs = qs.annotate(title_word_score=Value(0.0, output_field=FloatField()))

        qs = qs.filter(Q(title_word_score__gt=0) | Q(rank__gte=min_rank)).order_by(
            "-title_word_score", "-rank", "title", "id"
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


@function_tool
def search_offences(search_terms: str):
    """
    Search the offence database for offences matching one or more offence-related terms.

    Purpose
    -------
    This tool maps offence mentions found in a judgment to canonical offences
    stored in the database.

    The first comma-separated term is treated as the main offence label.
    Additional terms are treated as optional variants.

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
                "id": str,             # canonical offence ID
                "title": str,          # official offence title
                "description": str     # short excerpt from description
            },
            ...
        ]

    Notes
    -----
    - Results are ranked using PostgreSQL full-text search over the offence
      title and description.
    Ranking prefers:
    1. titles containing more words from the main term
    2. PostgreSQL full-text relevance
    3. stable ordering by title and id
    - Sorting is deterministic: rank DESC, title ASC, id ASC.
    """
    matches = search_offences_tool(search_terms)
    if not matches:
        return (
            "There are no offences in the database that match those search terms. You can try again with different"
            " search terms if you think the offence should be in the database. You must only try 2-3 times before"
            " concluding that there is no match."
        )
    return matches


JUDGMENT_EXTRACTION_PROMPT = """
# Role

You are a legal information extraction system. Your task is to extract structured information about offences
and sentencing from the text of a court judgment.

# Task

From the judgment text, identify the offences that the accused or appellant was charged with, convicted of,
acquitted of, or sentenced for. These offences must then be mapped to the corresponding offence IDs in the database
using the `search_offences` tool.

You must also extract any sentences imposed on the accused or appellant and ensure that each sentence is correctly
associated with the relevant offence.

Only return offences and sentences that relate directly to the accused or appellant in the case.

# Identifying Case Offences

You must extract only **case offences**, meaning offences that directly relate to the charges, convictions, acquittals,
or sentences involving the accused or appellant.

Judgments often mention other offences in passing. These incidental mentions must not be extracted. Incidental
references include examples used in legal reasoning, hypothetical discussions of the law, descriptions of offences
committed by other individuals, or general legal commentary that is not part of the charges against the accused or
appellant.

Your extraction should therefore focus only on offences that form part of the procedural history of the case.

For example, offences appearing in statements such as *“the appellant was charged with…”,
“the trial court convicted the accused of…”, “the accused was acquitted of…”*, or
*“the appellant was sentenced for…”* should be extracted.

Mentions of offences in explanations of legal principles, summaries of earlier authorities, or hypothetical examples
must be ignored.

# Mapping Offences to Database IDs

After identifying an offence in the judgment text, you must map it to a database offence using the `search_offences`
tool.

For each extracted offence, call `search_offences` using three to five concise keyword variants that represent the
offence. The search results should be used only to determine whether the extracted offence clearly corresponds to an
offence in the database.

An offence ID may only be assigned if one of the returned results is a clear semantic match to the extracted offence
wording. A clear match means that the candidate offence’s title or description closely corresponds to the offence
described in the judgment.

You are not allowed to invent offence IDs. You are also not allowed to output an offence ID unless that exact ID
appears in the results returned by the `search_offences` tool.

If the search returns no results, or if none of the results clearly match the extracted offence, the `offence_id`
must be set to `null`.

You must NOT assign an offence_id when:
- the search returns no results
- the returned offences are related but not the same
- the result is merely the “closest” available offence
- the wording in the judgment and the wording in the result refer to different offences

Example tool call:

<tool-call>
search_offences("robbery with violence, robbery, violent robbery, armed robbery")
</tool-call>

# Extracting Sentences and Matching Them to Offences

If the judgment text contains a sentence imposed on the accused or appellant, extract the sentence and attach it to the
appropriate offence.

Sentences generally fall into three categories: imprisonment, fines, and probation.

Imprisonment sentences are typically expressed with wording such as “sentenced to X years imprisonment” or
“imprisonment for X years or months.” Fines appear in phrases such as “fined KSh X” or “a fine of X.”
Probation sentences appear in phrases such as “placed on probation for X years or months.”

Where a sentence duration is expressed in years, convert it to months. For example, ten years must be represented as
120 months.

If the judgment explicitly states that a sentence is suspended, set `suspended = True`. If the judgment explicitly
states that the sentence represents the mandatory minimum for the offence, set `mandatory_minimum = True`. If this
information is not stated, use `null`.

# Handling Sentences That Are Not Clearly Linked to a Specific Offence

Some judgments state a sentence without explicitly linking it to a particular offence or count. When this occurs,
attempt to attach the sentence to the offence that most clearly corresponds to the conviction described in the judgment.

If the relationship between the sentence and the offence cannot be determined with confidence, attach the sentence to
the first extracted offence.


# Example 1: Simple Conviction and Sentence

<text>
The appellant was convicted of robbery with violence contrary to section 296(2) and sentenced to ten years imprisonment.
</text>

Tool call:

<tool-call>
search_offences("robbery with violence, robbery, violent robbery, armed robbery")
</tool-call>

Tool result:

<tool-output>
[
  {
    "id": 123,
    "title": "Robbery with Violence",
    "description": "An offence involving robbery with the use of violence as defined in section 296"
  }
]
</tool-output>

Because this clearly matches the offence “robbery with violence,” the offence is mapped to `offence_id = 123`.

The sentence “ten years imprisonment” is extracted and converted to 120 months.

# Example 2: Charge but Acquittal

<text>
The accused was charged with assault causing actual bodily harm but was acquitted by the trial court for lack of
sufficient evidence.
</text>

The offence **assault causing actual bodily harm** must still be extracted because it is part of the charges in the
case.

However, no sentence is extracted because the accused was acquitted.

# Example 3: Multiple Offences

<text>
The appellant was charged with burglary and stealing. The trial court convicted him of burglary and sentenced him to
five years imprisonment.
</text>

Both offences are case offences because they form part of the charges.

However, the sentence of five years imprisonment must be attached only to **burglary**, because that is the offence for
which the conviction occurred.

# Example 4: Fine Sentence

<text>
The accused pleaded guilty to the offence of careless driving and was fined KSh 20,000.
</text>

Extract the offence **careless driving** and the sentence **fine of 20000**.

# Example 5: Negative Example – Legal Discussion

<text>
In the case of R v Smith, the court explained that the offence of theft requires proof of dishonest appropriation.
</text>

The offence **theft** appears in this sentence but is part of a general legal explanation. It does not relate to the
accused in the present case and must therefore be ignored.

# Example 6: Negative Example – Hypothetical

<text>
If a person commits robbery but does not use violence, the offence may be simple robbery rather than robbery with
violence.
</text>

The offences **robbery** and **robbery with violence** appear only in a hypothetical explanation of the law and must
not be extracted.

# Example 7: Negative Example – Offence by Another Person

<text>
The prosecution witness testified that another suspect had earlier committed the offence of burglary in a
different incident.
</text>

The offence **burglary** mentioned here relates to another person and not to the accused in this case. It must be
ignored.

# Example 8: Appeal Context

<text>
The appellant appealed against his conviction for defilement and the sentence of fifteen years imprisonment imposed by
the trial court.
</text>

The offence **defilement** must be extracted because it is the conviction being appealed. The sentence of fifteen years
imprisonment must also be extracted and converted to 180 months.

# Example 9: Extracted Offence With No Database Match

<text>
The appellant was charged with assault causing actual bodily harm and sentenced to twelve months imprisonment.
</text>

Tool call:

<tool-call>
search_offences("assault causing actual bodily harm, assault, actual bodily harm, bodily injury")
</tool-call>

Tool result:

<tool-output>
[]
</tool-output>

Because the offence is clearly present in the judgment but no matching database offence exists,
the offence must still be extracted, but the offence_id must be null.

Extraction:

[
  {
    "offence_id": null,
    "offence_title": null,
    "extracted_offence": "assault causing actual bodily harm",
    "sentences": [
      {
        "sentence_type": "imprisonment",
        "duration_months": 12,
        "fine_amount": null,
        "suspended": false,
        "mandatory_minimum": null
      }
    ]
  }
]
"""


class SentenceExtraction(BaseModel):
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


class OffenceExtraction(BaseModel):
    offence_id: Optional[int] = Field(
        description="Offence ID from the database (from search_offences). Null if no clear match."
    )
    extracted_offence: str = Field(
        description="Clean offence label as written/normalized (no statute numbers)."
    )
    sentences: List[SentenceExtraction] = []


class OutcomeExtraction(BaseModel):
    extracted_outcome: str = Field(
        description="""Canonical outcome label. Must exactly match one of the canonical outcome names provided in the
                        prompt.
                    """
    )


class JudgmentOffenceExtraction(BaseModel):
    offences: List[OffenceExtraction] = []


class JudgmentOutcomeExtraction(BaseModel):
    outcomes: List[OutcomeExtraction] = []


offence_extraction_agent = Agent(
    name="Offence + Sentence Extractor",
    instructions=JUDGMENT_EXTRACTION_PROMPT,
    tools=[search_offences],
    output_type=JudgmentOffenceExtraction,
    model_settings=ModelSettings(reasoning=Reasoning(effort="medium", summary="auto")),
    model="gpt-5-mini",
)


def extract_offences_and_sentences(judgment_text: str) -> JudgmentOffenceExtraction:
    result = Runner.run_sync(
        offence_extraction_agent,
        judgment_text,
    )
    log_agent_reasoning(result)
    log.info("Extraction result: %s", result.final_output)
    return result.final_output


OUTCOME_EXTRACTION_PROMPT = """
# Role

You are a legal information extraction system. Your task is to extract structured information about case outcomes
from the text of a court judgment.

# Task

From the judgment text, identify the dispositive outcomes for the present case.

Only extract outcomes that describe the actual result of the present judgment or the result being affirmed, varied,
or overturned on appeal.

The outcome labels you return must come from this canonical list only:

{allowed_case_outcomes}

# Identifying Case Outcomes

Typical examples include outcomes such as an appeal being dismissed or allowed, a conviction being upheld or quashed,
a sentence being affirmed, reduced, enhanced, or set aside, or an acquittal being entered.

Outcomes may be multiple. For example, a judgment may dismiss an appeal against conviction but allow an appeal against
sentence, or it may quash a conviction and set aside the sentence. Return each distinct canonical outcome that is
clearly supported by the judgment text.

Do not extract generic narrative statements that are not dispositive outcomes.

Focus on the final operative result, not every intermediate discussion.

When you return `extracted_outcome`, it must be exactly one of the canonical outcome labels above.

Do not invent new labels, paraphrase the labels, or return near-matches. If none of the canonical labels fit, return
no outcome for that point.
"""


def extract_outcomes(judgment_text: str) -> JudgmentOutcomeExtraction:
    canonical_outcome_names = list(
        Outcome.objects.order_by("name").values_list("name", flat=True)
    )
    if not canonical_outcome_names:
        log.info("No canonical outcomes configured; skipping outcome extraction.")
        return JudgmentOutcomeExtraction()

    outcome_extraction_agent = Agent(
        name="Outcome Extractor",
        instructions=OUTCOME_EXTRACTION_PROMPT.format(
            allowed_case_outcomes="\n".join(
                f"- {outcome}" for outcome in canonical_outcome_names
            )
        ),
        tools=[],
        output_type=JudgmentOutcomeExtraction,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto")
        ),
        model="gpt-5-mini",
    )

    result = Runner.run_sync(
        outcome_extraction_agent,
        judgment_text,
    )
    log_agent_reasoning(result)
    log.info("Outcome extraction result: %s", result.final_output)
    return result.final_output


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


CASE_META_PROMPT = """
# Role

You are a legal information extraction system. Your task is to extract the **case type** and **filing year** from the
text of a court judgment.

# Task

From the judgment text, determine:

- `case_type`: `criminal`, `civil`, or `null` if the case type cannot be determined with confidence.
- `filing_year`: the four-digit year in which the case was filed, registered, or lodged. If the filing year cannot be
clearly determined from the text, return `null`.

Only extract information that is clearly supported by the text of the judgment.

# Determining the Case Type

A case should be classified as **criminal** if the judgment concerns criminal charges, criminal liability, or criminal
sentencing involving an accused or appellant. Criminal cases typically involve prosecution by the State and references
to criminal statutes.

Indicators of a criminal case include language such as *“accused,” “convicted,” “acquitted,” “sentenced,”
“criminal appeal,”* or references to criminal legislation such as the Penal Code or other criminal statutes.
References to the prosecution or the State are also strong indicators of a criminal case.

A case should be classified as **civil** if it involves disputes between parties such as plaintiffs and defendants
concerning rights, obligations, or remedies under civil law. Civil judgments typically involve matters such as
contracts, property disputes, tort claims, damages, or injunctions.

Indicators of a civil case include references to *“plaintiff,” “defendant,” “claim,” “damages,” “breach of contract,”
“injunction,”* or other forms of civil relief.

Constitutional petitions and judicial review matters are not automatically classified as civil. They should only be
classified as civil if the judgment clearly frames the matter as a civil dispute.

If the case type cannot be determined with reasonable confidence, return `case_type = null`.

# Determining the Filing Year

The `filing_year` is the year in which the case was filed, registered, or lodged in court.

You may extract the filing year only if the text clearly indicates the filing or registration year of the case.
This commonly appears in the case number or in explicit statements describing when the case was filed.

Common examples include case numbers such as:

<text>
Criminal Appeal No. 12 of 2019
</text>

or

<text>
Civil Appeal No. 3 of 2020
</text>

The filing year may also appear in statements such as:

<text>
The appeal was filed in 2018.
</text>

or

<text>
The petition was lodged in 2021.
</text>

If the judgment text contains only dates related to the offence, incident, or judgment (for example, the date of the
crime or the date the judgment was delivered), these must **not** be treated as the filing year.

If there is no clear indication of the filing year, return `filing_year = null`.

# Example 1: Criminal Appeal with Filing Year

<text>
Criminal Appeal No. 12 of 2019
The appellant was convicted of robbery with violence and sentenced to ten years imprisonment.
</text>

Extraction:

- `case_type = criminal`
- `filing_year = 2019`

# Example 2: Civil Appeal with Filing Year

<text>
Civil Appeal No. 3 of 2020
The appellant challenges the trial court's award of damages for breach of contract.
</text>

Extraction:

- `case_type = civil`
- `filing_year = 2020`

# Example 3: Criminal Case Without Filing Year

<text>
The accused was charged with the offence of defilement contrary to section 8 of the Sexual Offences Act.
</text>

Extraction:

- `case_type = criminal`
- `filing_year = null`

# Example 4: Civil Dispute Without Filing Year

<text>
The plaintiff filed a suit seeking damages for breach of contract and an order of injunction against the defendant.
</text>

Extraction:

- `case_type = civil`
- `filing_year = null`

# Example 5: Filing Year Mentioned in Text

<text>
The petition was lodged in 2021 and challenges the constitutionality of the impugned regulation.
</text>

Extraction:

- `case_type = null`
- `filing_year = 2021`

# Example 6: Negative Example – Incident Date

<text>
The offence was committed on 14 March 2019 and the accused was later arrested.
</text>

The date refers to when the offence occurred, not when the case was filed.

Extraction:

- `case_type = criminal`
- `filing_year = null`

# Example 7: Negative Example – Judgment Date

<text>
Judgment delivered on 7 July 2022.
</text>

This date refers to when the judgment was delivered and does not indicate the filing year.

Extraction:

- `case_type = null`
- `filing_year = null`
"""

case_type_extraction_agent = Agent(
    name="Case Type + Filing Year Extractor",
    instructions=CASE_META_PROMPT,
    output_type=CaseMetaExtraction,
    model_settings=ModelSettings(reasoning=Reasoning(effort="medium", summary="auto")),
    model="gpt-5-mini",
)


def extract_case_type_filing_year(judgment_text: str) -> CaseMetaExtraction:
    result = Runner.run_sync(
        case_type_extraction_agent,
        judgment_text,
    )
    log_agent_reasoning(result)
    log.debug("Extraction result: %s", result.final_output)
    return result.final_output
