"""
OpenAI Agents-based document chat helpers.
"""

import os
from pathlib import Path

from agents import Agent, SQLiteSession
from agents.items import MessageOutputItem
from asgiref.sync import sync_to_async
from cobalt.uri import FrbrUri
from django.conf import settings
from langfuse import Langfuse

from peachjam.models import Judgment, Legislation
from peachjam_ml.chat.tools import (
    DocumentChatContext,
    get_citator_citations,
    get_tools_for_document,
)

# TODO: better sessions
DEFAULT_SESSION_DB_PATH = Path(settings.BASE_DIR) / "chat_sessions.sqlite3"


# Langfuse uses environment variables to configure itself
# we block elasticsearch-api instrumentation which comes through from the opentelemetry data
langfuse = Langfuse(blocked_instrumentation_scopes=["elasticsearch-api"])


def get_session_db_path() -> str:
    db_path = (
        settings.PEACHJAM.get("CHAT_SESSION_DB_PATH")
        if hasattr(settings, "PEACHJAM")
        else None
    )
    if not db_path:
        db_path = DEFAULT_SESSION_DB_PATH
    return str(db_path)


def get_session(thread) -> SQLiteSession:
    return SQLiteSession(str(thread.id), db_path=get_session_db_path())


class DocumentChat:
    INITIAL_PROMPT_NAME = "chat/document/initial"
    PROMPT_CACHE_TTL_SECS = 30 if settings.DEBUG else 60
    CHAT_MODEL_NAME = "gpt-5-mini"

    def __init__(self, thread):
        self.thread = thread
        self.document = thread.document
        self.user = thread.user
        self.context = DocumentChatContext(
            document_id=self.document.id,
            user_id=self.user.id,
            thread_id=str(thread.id),
        )
        self.session = get_session(thread)
        self.agent = self.build_agent()

    async def setup(self) -> None:
        """Add initial message to the session if it's empty, containing metadata about the document."""
        items = await self.session.get_items()
        if items:
            return

        metadata_items = await sync_to_async(self.build_metadata_items)()
        await self.session.add_items(metadata_items)

    def build_metadata_items(self) -> list[dict]:
        return [{"role": "developer", "content": self.doc_metadata_text()}]

    def build_agent(self) -> Agent[DocumentChatContext]:
        return Agent(
            name=os.environ.get("CHAT_ASSISTANT_NAME", "document-chat"),
            instructions=self.compile_initial_prompt(),
            tools=get_tools_for_document(self.document),
            model=self.CHAT_MODEL_NAME,
        )

    def compile_initial_prompt(self) -> str:
        app = settings.PEACHJAM["APP_NAME"]
        prompt = langfuse.get_prompt(
            self.INITIAL_PROMPT_NAME, cache_ttl_seconds=self.PROMPT_CACHE_TTL_SECS
        )
        return prompt.compile(app=app, user_name=self.user.get_full_name())

    def doc_metadata_text(self) -> str:
        metadata = [
            f"Title: {self.document.title}",
            f"Date of this version: {self.document.date.isoformat()}",
            f"Type of document: {self.document.nature}",
        ]

        if self.document.citation and self.document.citation != self.document.title:
            metadata.append(f"Citation: {self.document.citation}")

        alternative_names = self.document.alternative_names.all()
        if alternative_names:
            metadata.append(
                "Also referred to/cited as: "
                + "; ".join(an.title for an in alternative_names)
            )

        if isinstance(self.document, Legislation):
            if self.document.repealed:
                metadata.append("This legislation has been repealed.")
                repeal_info = self.document.metadata_json.get("repeal", None)
                if repeal_info:
                    metadata.append(
                        f"Repealed on {repeal_info['date']} by {repeal_info['repealing_title']}."
                    )

            if self.document.commenced:
                if self.document.metadata_json.get("commenced_in_full"):
                    metadata.append(
                        f"This legislation commenced on {self.document.metadata_json['commencement_date']}. "
                        "Some provisions may have commenced after this date. "
                        "More information on commencements may be available from other tools."
                    )
                else:
                    metadata.append(
                        f"This legislation partially commenced on {self.document.metadata_json['commencement_date']}. "
                        "More information on commencements may be available from other tools."
                    )
            else:
                metadata.append("This legislation has not yet commenced.")

        elif isinstance(self.document, Judgment):
            if self.document.anonymised:
                metadata.append(
                    "This judgment has anonymised to protect personal information in compliance with the law."
                )
            if self.document.court:
                metadata.append(f"Court: {self.document.court.name}")
            if self.document.judges:
                metadata.append(
                    "Judges: "
                    + ", ".join(judge.name for judge in self.document.judges.all())
                )
            if self.document.blurb:
                metadata.append(f"Short summary: {self.document.blurb}")
            if self.document.flynote:
                metadata.append(f"Flynote: {self.document.flynote}")
            if self.document.case_summary:
                metadata.append(f"Case summary: {self.document.case_summary}")
            if self.document.issues:
                metadata.append("Issues: \n  * " + "\n  * ".join(self.document.issues))
            if self.document.held:
                metadata.append("Held: \n  * " + "\n  * ".join(self.document.held))
            if self.document.order:
                metadata.append(f"Order: {self.document.order}")

        msg = (
            "Here is some information about the document to help answer questions:\n\n"
            + "\n".join(metadata)
        )
        return msg

    def markup_refs(self, text: str) -> str:
        """Markup refs in the AI response message."""
        if not text or len(text.strip()) <= 5:
            return text

        resp = get_citator_citations(self.document.expression_frbr_uri, text)
        # get citations, last one first
        citations = sorted(resp["citations"], key=lambda c: c["end"], reverse=True)
        for citation in citations:
            href = citation["href"]
            try:
                uri = FrbrUri.parse(href)
                # is it a local reference?
                if uri.portion and uri.work_uri(False) == self.document.work_frbr_uri:
                    href = f"#{uri.portion}"
            except ValueError:
                continue

            # wrap markdown-style links around cited text based on offset and length
            text = (
                text[: citation["start"]]
                + "["
                + citation["text"]
                + "]("
                + href
                + ")"
                + text[citation["end"] :]
            )

        return text


def extract_assistant_response(result) -> dict:
    for item in reversed(result.new_items):
        if isinstance(item, MessageOutputItem):
            return {
                "id": item.raw_item.id,
                "role": "ai",
                "content": result.final_output,
            }
