import json
import logging
import os
from typing import Optional

from agents import Agent, ModelSettings, Runner, RunResult, function_tool
from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from openai.types import Reasoning
from pydantic import BaseModel

from peachjam.analysis.agents import log_agent_reasoning
from peachjam.langfuse import PROMPT_CACHE_TTL_SECS, langfuse
from peachjam.models import Flynote as FlynoteModel

log = logging.getLogger(__name__)


class SummariserError(Exception):
    pass


class JudgmentSummary(BaseModel):
    issues: list[str]
    held: list[str]
    order: str
    summary: str
    flynote: str
    blurb: str


class Flynote(BaseModel):
    flynote: str


FLYNOTE_MATCH_PROMPT = """
You must now align the flynotes you have suggested with the flynote components that are in the database. This helps
ensure that flynotes are consistent and well-categorised, and avoids issues like typos or spelling differences.
The first two components are more structured than the second two, so it's more important to match those to the database.

For flynote component 1, you MUST choose an appropriate entry from the list of top-level flynotes provided below that
most closely matches your flynote component 1.

For flynote components 2, 3 and 4 you must use the search_flynotes tool to find the closest matching flynote in the
database. Consider the text and semantics of the flynote when making your choice and ensure that the chosen flynotes
(either from the list, or your original suggestion if there is no good match) still accurately reflect the content
of the judgment. The search results include the number of documents tagged with each flynote. Use this as a guide for
which flynote to choose if there are multiple good matches, since it's better to use flynotes that are already commonly
used, but you should prioritise the semantic match over the number of documents.

The flynote database is stored in a tree structure, where each flynote has a parent (except for component 1, which are
top-level flynotes). When using the search_flynotes tool for components 2, 3 and 4, you must specify the id of the
previous component as the parent_id. This ensures the tool searches the children of that flynote.

Adhere to the following rules when matching flynotes to the database:

1. Flynote component 1: you MUST choose an appropriate entry from the list provided below that most closely matches
your flynote component 1. You MUST NOT use a flynote component 1 that doesn't exist in the database. There is no need
to use the search_flynotes tool because the full list is provided below.

2. Flynote component 2: you SHOULD choose an appropriate entry from the database that most closely matches your
flynote component 2. If there is not a good match, use your original suggestion, but only if there is not a good match.
About 75% of the time there should be a good match for flynote component 2.

3. Flynote components 3 and 4: you MAY choose an appropriate entry from the database that most closely matches your
flynote components 3 and 4, but only if there is a good match. If there is not a good match, use your original
suggestions for flynote components 3 and 4.

4. For components 2 or 3, if you choose not to use a flynote from the database, then you will not have an appropriate
parent_id for the next component. In that case, simply use your original flynotes for the subsequent components, and do
not use the search_flynotes tool for those components.

You must follow this process for each newline-separated flynote that you generated.

When you're done, return your new flynotes, one per line.

# Using the search_flynotes tool

When using the search_flynotes tool, you can provide a list of keywords (or phrases) to search for. Always provide the
the actual flynote as one of the keywords, and then include 2-5 other keywords that are relevant to the flynote and
might help the search. Keywords are case insensitive. The more relevant keywords you provide, the broader the results.

# Example

Your suggested flynote:

<flynote>
Execution — Writs and quantification — Whether writs for statutory post-judgment interest require supporting affidavits — Uniform Rules of Court
</flynote>

Components:

1. Execution
2. Writs and quantification
3. Whether writs for statutory post-judgment interest require supporting affidavits
4. Uniform Rules of Court

For component 1, you look at the list of top-level flynotes provided and choose the one that most closely matches
"Execution".

For component 2, use the search_flynotes tool with keywords like ["Writs and quantification", "Writs", "Quantification"]
and parent_id=10 (assuming 10 is the id of the chosen flynote for component 1). The database returns two close matches:

- (id: 1202, documents: 12): Writs
- (id: 1494, documenst: 392): Writs/quantification

The best match is "Writs/quantification" since it's a very close match and many documents use it, so you use
"Writs/quantification" for component 2.

For component 3, you use the search_flynotes tool again with keywords like
["Whether writs for statutory post-judgment interest require supporting affidavits", "post-judgment interest", "writs",
"quantification"] and parent_id=1494.

The database returns no good matches, so you choose to keep your original suggestion. You also don't have an
appropriate parent_id for component 4, so you keep your original suggestion for component 4 as well.

Your final flynote is now:

<flynote>
Execution — Writs/quantification — Whether writs for statutory post-judgment interest require supporting affidavits — Uniform Rules of Court
</flynote>
"""  # noqa: E501


def search_flynotes_tool(keywords: list[str], parent_id: int) -> str:
    log.debug("search for flynotes: parent_id=%s, keywords=%s", parent_id, keywords)

    terms = [(term or "").strip() for term in keywords]
    terms = [term for term in terms if term]
    terms = list(dict.fromkeys(terms))

    if not terms:
        return "You must provide at least one keyword to search for. Please try again with relevant keywords."

    primary_term = terms[0]
    limit = 30
    min_similarity = 0.1

    parent = FlynoteModel.objects.filter(pk=parent_id).first()
    if not parent:
        return (
            "You provided an invalid parent_id that doesn't exist in the database, so no search was performed. "
            "Please check the parent_id and try again."
        )

    # Flynote names are short canonical labels. Trigram similarity naturally favours
    # exact and near-exact matches, while still handling punctuation and hyphenation
    # differences such as "post judgment" vs "post-judgment".
    qs = parent.get_children().annotate(
        similarity=TrigramSimilarity("name", primary_term),
    )
    # Require a minimum similarity so that loosely related long titles do not
    # dominate the results.
    qs = qs.filter(similarity__gte=min_similarity)
    qs = qs.select_related("document_count_cache")
    # NOTE: if this fails with a psql type error, ensure that the pg_trgm extension is installed:
    #   CREATE EXTENSION IF NOT EXISTS pg_trgm;
    qs = qs.order_by("-similarity", "name", "id")[:limit]

    # sort by document count descending
    matches = sorted(
        list(qs),
        key=lambda flynote: getattr(flynote.document_count_cache, "count", 0),
        reverse=True,
    )

    matches = [
        f"(id: {flynote.pk}, documents: {getattr(flynote.document_count_cache, 'count', 0)}): {flynote.name}"
        for flynote in matches
    ]
    log.debug("flynote search results: %s", matches)

    if not matches:
        return (
            "There are no flynotes that match those search terms. You can try again with different search terms. "
            "You must only try 2-3 times before concluding that there is no match."
        )

    return "\n".join(matches)


@function_tool
def search_flynotes(keywords: list[str], parent_id: int) -> str:
    """
    Search the flynote database for flynotes matching the provided keywords, looking at children of parent_id, if given.
    Use this tool to find search the flynote tree for flynotes similar to the flynote components you have generated.

    - For keywords, provide your original flynote component text as the first item, then any other relevant keywords
    that might help the search. For example, if your flynote component is "Writs and quantification",
    you might provide keywords like ["Writs and quantification", "Writs", "Quantification"].
    - keywords are case insensitive
    - for the parent_id, provide the id of the parent flynote to search its children.
    """
    try:
        return search_flynotes_tool(keywords, parent_id)
    finally:
        connection.close()


class JudgmentSummariser:
    default_llm_model = "gpt-5-mini"
    llm_model = None
    summary_prompt_name = "summarise/judgment"
    summary_prompt_str = None
    prompt_cache_ttl_seconds = PROMPT_CACHE_TTL_SECS
    # Should the summariser attempt to match flynotes in the generated summary to flynotes in the database, and replace
    # them with the matched flynotes from the database? This can help improve consistency and categorization of
    # flynotes, but it requires that there is an initial set of top-level flynotes in the database to match against,
    # so it's behind a feature flag.
    match_flynotes_to_db = settings.PEACHJAM["SUMMARISE_USE_FLYNOTE_TREE"]
    agent: Optional[Agent] = None
    run_result: Optional[RunResult] = None
    max_top_level_flynotes = 50

    def __init__(self):
        self.summary_language = settings.PEACHJAM["SUMMARISER_LANGUAGE"]
        self.summary_prompt = None
        if self.enabled():
            self.summary_prompt = langfuse.get_prompt(
                self.summary_prompt_name,
                cache_ttl_seconds=self.prompt_cache_ttl_seconds,
                fallback=self.summary_prompt_str,
            )

    def enabled(self):
        return bool(
            os.environ.get("OPENAI_API_KEY")
            and os.environ.get("LANGFUSE_PUBLIC_KEY")
            and os.environ.get("LANGFUSE_SECRET_KEY")
            and settings.PEACHJAM["SUMMARISE_JUDGMENTS"]
        )

    def summarise_judgment(self, document) -> JudgmentSummary:
        if not self.enabled():
            raise SummariserError("Summariser service not configured")

        doc_content = document.get_or_create_document_content()
        text = doc_content.get_content_as_text()
        if not text:
            raise SummariserError("Document doesn't have any text to summarise.")

        self.create_agent(document.jurisdiction.name)

        try:
            result = self.summarise(
                expression_frbr_uri=document.expression_frbr_uri,
                text=text,
                language=self.summary_language,
            )
        except Exception as exc:
            log.error(exc, exc_info=exc)
            raise SummariserError(f"Error generating judgment summary: {exc}") from exc

        return result

    def create_agent(self, jurisdiction):
        self.agent = Agent(
            name="Judgment Summariser",
            instructions=self.get_summary_prompt_str(jurisdiction=jurisdiction),
            output_type=JudgmentSummary,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="medium", summary="auto"),
                response_include=["reasoning.encrypted_content"],
                store=False,
            ),
            model=self.get_model(),
        )

    def get_summary_prompt_str(self, **context):
        return self.summary_prompt_str or self.summary_prompt.compile(**context)

    def get_model(self):
        return (
            self.llm_model
            or self.summary_prompt.config.get("model")
            or self.default_llm_model
        )

    @staticmethod
    def normalise_flynote_text(flynote):
        if not flynote:
            return ""

        from peachjam.analysis.flynotes import FlynoteParser

        return FlynoteParser().normalise_multiline_text(flynote)

    def normalise_summary(self, summary):
        summary.flynote = self.normalise_flynote_text(summary.flynote)
        return summary

    def summarise(self, expression_frbr_uri, text, language=None) -> JudgmentSummary:
        log.info("Generating judgment summary")

        with langfuse.start_as_current_observation(
            name="summarise_judgment",
            as_type="generation",
            input={"expression_frbr_uri": expression_frbr_uri},
            prompt=self.summary_prompt,
        ) as generation:
            summary = self.generate_summary(text)
            summary = self.match_flynotes(summary)
            summary = self.translate_summary(summary, language)
            summary = self.normalise_summary(summary)

            generation.update(output=summary.model_dump())

        log.info("Done")
        return summary

    def generate_summary(self, text):
        self.run_result = Runner.run_sync(self.agent, input=text)
        log_agent_reasoning(self.run_result)
        return self.run_result.final_output

    def match_flynotes(self, summary):
        """If enabled, attempt to match flynotes in the generated summary to flynotes in the database, and replace the
        generated flynote text with the matched flynote text from the database."""
        if not self.match_flynotes_to_db:
            return summary

        log.debug(f"Matching flynotes to db:\n---\n{summary.flynote}\n---")

        input = self.run_result.to_input_list()
        input.append(
            {
                "role": "developer",
                "content": FLYNOTE_MATCH_PROMPT + self.top_level_flynotes_prompt(),
            }
        )

        # give the agent tools and change its output type
        agent = self.agent.clone(tools=[search_flynotes], output_type=Flynote)
        run_result = Runner.run_sync(agent, input)
        log_agent_reasoning(run_result)

        summary.flynote = run_result.final_output.flynote
        log.debug(f"Matched flynotes:\n---\n{summary.flynote}\n---")

        return summary

    def top_level_flynotes_prompt(self):
        flynotes = (
            FlynoteModel.objects.filter(depth=1)
            .select_related("document_count_cache")
            .order_by("-document_count_cache__count", "name")[
                : self.max_top_level_flynotes
            ]
        )
        flynote_list = "\n".join(
            f"- (id {flynote.pk}): {flynote.name}" for flynote in flynotes
        )
        return (
            "\n\n# Top-level flynotes\n\nHere is the list of top-level flynotes you can choose from for flynote "
            f"component 1:\n{flynote_list}\n"
        )

    def translate_summary(self, summary, language):
        if not language or language == "English":
            return summary

        log.info(f"Translating judgment summary into {language}")

        # build on the original input for the translation, to give the model more context to work with
        input = self.run_result.to_input_list()
        input.append(
            {
                "role": "developer",
                "content": (
                    "Here is the latest summary:\n\n"
                    + json.dumps(summary.model_dump(), indent=2)
                    + "\n\n",
                    f"Now translate all fields of the summary into {language}. Do not translate Latin"
                    f" words, keep them in their original form.",
                ),
            }
        )

        self.run_result = Runner.run_sync(self.agent, input)
        return self.run_result.final_output
