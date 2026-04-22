import logging
import os
from typing import Optional

from agents import Agent, ModelSettings, Runner, RunResult
from django.conf import settings
from openai.types import Reasoning
from pydantic import BaseModel

from peachjam.analysis.agents import log_agent_reasoning
from peachjam.langfuse import PROMPT_CACHE_TTL_SECS, langfuse

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


class JudgmentSummariser:
    default_llm_model = "gpt-5-mini"
    llm_model = None
    summary_prompt_name = "summarise/judgment"
    summary_prompt_str = None
    prompt_cache_ttl_seconds = PROMPT_CACHE_TTL_SECS
    match_flynotes_to_db = settings.PEACHJAM["SUMMARISER_MATCH_FLYNOTES_TO_DB"]
    agent: Optional[Agent] = None
    run_result: Optional[RunResult] = None

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

        # TODO: update input
        input = self.run_result.to_input_list()
        input.append(
            {
                "role": "developer",
                "content": "xxx",
            }
        )

        # give the agent tools and change its output type
        # TODO tools
        agent = self.agent.clone(tools=[], output_type=Flynote)
        run_result = Runner.run_sync(agent, input)
        log_agent_reasoning(self.run_result)
        summary.flynote = run_result.final_output.flynote

        log.debug(f"Matched flynotes:\n---\n{summary.flynote}\n---")

        return summary

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
                    f"Now translate all fields of your summary into {language}. Do not translate Latin"
                    f" words, keep them in their original form."
                ),
            }
        )

        self.run_result = Runner.run_sync(self.agent, input)
        return self.run_result.final_output
