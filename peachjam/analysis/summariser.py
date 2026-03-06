import json
import logging
import os

from django.conf import settings
from openai import OpenAI
from pydantic import BaseModel

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


class JudgmentSummariser:
    default_llm_model = "gpt-5-mini"
    llm_model = None
    summary_prompt_name = "summarise/judgment"
    summary_prompt_str = None
    prompt_cache_ttl_seconds = PROMPT_CACHE_TTL_SECS

    def __init__(self):
        self.summary_language = settings.PEACHJAM["SUMMARISER_LANGUAGE"]
        self.summary_prompt = None
        if self.enabled():
            self.openai = OpenAI()
            self.summary_prompt = langfuse.get_prompt(
                self.summary_prompt_name,
                cache_ttl_seconds=self.prompt_cache_ttl_seconds,
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

        try:
            result = self.summarise(
                expression_frbr_uri=document.expression_frbr_uri,
                text=text,
                language=self.summary_language,
            )
        except Exception as exc:
            raise SummariserError(f"Error generating judgment summary: {exc}") from exc

        return result

    def get_summary_prompt_str(self, **context):
        return self.summary_prompt_str or self.summary_prompt.compile(**context)

    def get_model(self):
        return (
            self.llm_model
            or self.summary_prompt.config.get("model")
            or self.default_llm_model
        )

    def summarise(self, expression_frbr_uri, text, language=None) -> JudgmentSummary:
        log.info("Generating judgment summary locally")

        with langfuse.start_as_current_observation(
            name="summarise_judgment",
            as_type="generation",
            input={"expression_frbr_uri": expression_frbr_uri},
            prompt=self.summary_prompt,
        ) as generation:
            input = [{"role": "user", "content": text}]
            response = self.openai.responses.parse(
                model=self.get_model(),
                instructions=self.get_summary_prompt_str(),
                input=input,
                text_format=JudgmentSummary,
                store=False,
            )
            summary = response.output_parsed

            if language and language != "English":
                log.info(f"Translating judgment summary into {language}")
                # build on the original input for the translation, to give the model more context to work with
                input.extend(
                    [
                        {
                            "role": "assistant",
                            "content": json.dumps(summary.model_dump(), indent=2),
                        },
                        {
                            "role": "developer",
                            "content": (
                                f"Now translate all fields of your summary into {language}. Do not translate Latin"
                                f" words, keep them in their original form."
                            ),
                        },
                    ]
                )

                completion = self.openai.responses.parse(
                    model=self.get_model(),
                    input=input,
                    text_format=JudgmentSummary,
                    store=False,
                )
                summary = completion.output_parsed

            generation.update(output=summary.model_dump())
            log.info("Done")
            return summary
