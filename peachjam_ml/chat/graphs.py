"""
This module defines the chat graph for document-based chats using Langgraph and Langchain.

# How a chat works

A single chat interaction (human question + AI reply) is a run of a graph. The graph is made up of nodes, each of which
is a function that takes in a state and returns a new state. The state is a TypedDict that contains the chat messages
and any other relevant information (e.g. document ID, user ID).

For example, when a chat starts one of the first nodes adds a system prompt to the messages state, which describes
to the LLM who it is talking to and the context of the document. Another node adds metadata about the document, also
as a system message.

One of the nodes is the main chatbot node, which takes in the current messages state, appends the user's query as a
new human message, and then calls the LLM (with tools) to get a response. The response is appended as an AI message to
the messages state.

# Follow-up queries

Follow-up queries in the same chat session work by re-running the graph with the full message history. Follow-up runs
don't need to re-inject the system prompt or document metadata, as these are already in the message history. The graph
has conditional edges to skip the initial prompt and metadata nodes if there are already messages in the state,
jumping immediately to the chatbot node.

# Tools

The chatbot node uses an LLM that has been augmented with tools. If the LLM decides to use a tool, the graph has
conditional edges to route to a tool node, which executes the tool and returns the result to the chatbot node for
inclusion in the message history.

For example, there is a tool that can answer questions about the document content. If the user asks a question
that requires knowledge of the document, the LLM can invoke this tool to get the answer. This is better than
always including the full document text in the prompt, which may exceed token limits.

# Persistence

Each time the graph is run, the state is saved to a Postgres database using Langgraph's PostgresSaver. When the user
returns and wants to ask a follow-up question, we provide the same thread_id to the graph run, which allows it to
load the previous state from the database and continue the conversation.

# Langfuse

The module also integrates with Langfuse for prompt management and observability of chat interactions. This makes
debugging and monitoring chat sessions easier.

# Configuration

The following must be configured as ENV variables:

* CHAT_ENABLED = true
* LANGFUSE_HOST = https://cloud.langfuse.com
* LANGFUSE_PUBLIC_KEY
* LANGFUSE_SECRET_KEY
* OPENAI_API_KEY
* CHAT_ASSISTANT_NAME (optional)
"""

import os
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator, Tuple, TypedDict

from cobalt.uri import FrbrUri
from django.conf import settings
from django.contrib.auth.models import User
from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import StateSnapshot

from peachjam.models import CoreDocument, Judgment, Legislation
from peachjam_ml.chat.tools import (
    ALL_TOOLS,
    get_citator_citations,
    get_tools_for_document,
)

INITIAL_PROMPT_NAME = "chat/document/initial"
PROMPT_CACHE_TTL_SECS = 30 if settings.DEBUG else 60


class UserMessage(TypedDict):
    content: str
    id: str


class DocumentChatState(MessagesState):
    document_id: int
    user_id: int
    user_message: UserMessage


# Langfuse uses environment variables to configure itself
# we block elasticsearch-api instrumentation which comes through from the opentelemetry data
langfuse = Langfuse(blocked_instrumentation_scopes=["elasticsearch-api"])
langfuse_callback = CallbackHandler()


# we must supply a non-blank API key otherwise the client complains (the key is not validated until a request is made)
chat_llm = init_chat_model(
    "openai:gpt-5-mini", temperature=0, api_key=os.environ.get("OPENAI_API_KEY") or "-"
)


async def chatbot(state: DocumentChatState):
    document = await CoreDocument.objects.aget(pk=state["document_id"])
    llm_with_tools = chat_llm.bind_tools(get_tools_for_document(document))

    state["messages"].append(
        HumanMessage(
            content=state["user_message"]["content"], id=state["user_message"]["id"]
        )
    )
    return {"messages": [await llm_with_tools.ainvoke(state["messages"])]}


def initial_prompt(state: DocumentChatState):
    user = User.objects.get(pk=state["user_id"])
    app = settings.PEACHJAM["APP_NAME"]
    prompt = langfuse.get_prompt(
        INITIAL_PROMPT_NAME, cache_ttl_seconds=PROMPT_CACHE_TTL_SECS
    )
    prompt = prompt.compile(
        app=app,
        user_name=user.get_full_name(),
    )
    return {"messages": [SystemMessage(content=prompt)]}


def doc_metadata(state: DocumentChatState):
    document = CoreDocument.objects.get(pk=state["document_id"])

    metadata = [
        f"Title: {document.title}",
        f"Date of this version: {document.date.isoformat()}",
        f"Type of document: {document.nature}",
    ]

    if document.citation and document.citation != document.title:
        metadata.append(f"Citation: {document.citation}")

    alternative_names = document.alternative_names.all()
    if alternative_names:
        metadata.append(
            "Also referred to/cited as: "
            + "; ".join(an.title for an in alternative_names)
        )

    if isinstance(document, Legislation):
        if document.repealed:
            metadata.append("This legislation has been repealed.")
            repeal_info = document.metadata_json.get("repeal", None)
            if repeal_info:
                metadata.append(
                    f"Repealed on {repeal_info['date']} by {repeal_info['repealing_title']}."
                )

        if document.commenced:
            if document.metadata_json.get("commenced_in_full"):
                metadata.append(
                    f"This legislation commenced on {document.metadata_json['commencement_date']}. Some provisions "
                    "may have commenced after this date."
                    "More information on commencements may be available from other tools."
                )
            else:
                metadata.append(
                    f"This legislation partially commenced on {document.metadata_json['commencement_date']}. "
                    "More information on commencements may be available from other tools."
                )
        else:
            metadata.append("This legislation has not yet commenced.")

    elif isinstance(document, Judgment):
        if document.anonymised:
            metadata.append(
                "This judgment has anonymised to protect personal information in compliance with the law."
            )
        if document.court:
            metadata.append(f"Court: {document.court.name}")
        if document.judges:
            metadata.append(
                "Judges: " + ", ".join(judge.name for judge in document.judges.all())
            )
        if document.blurb:
            metadata.append(f"Short summary: {document.blurb}")
        if document.flynote:
            metadata.append(f"Flynote: {document.flynote}")
        if document.case_summary:
            metadata.append(f"Case summary: {document.case_summary}")
        if document.issues:
            metadata.append("Issues: \n  * " + "\n  * ".join(document.issues))
        if document.held:
            metadata.append("Held: \n  * " + "\n  * ".join(document.held))
        if document.order:
            metadata.append(f"Order: {document.order}")

    msg = (
        "Here is some information about the document to help answer questions:\n\n"
        + "\n".join(metadata)
    )
    return {"messages": [SystemMessage(content=msg)]}


def markup_refs(state: DocumentChatState):
    """Markup refs in the last AI response message."""
    message = state["messages"][-1]
    if message.type == "ai" and len(message.content.strip()) > 5:
        doc = CoreDocument.objects.get(pk=state["document_id"])
        resp = get_citator_citations(doc.expression_frbr_uri, message.content)
        # get citations, last one first
        citations = sorted(resp["citations"], key=lambda c: c["end"], reverse=True)
        for citation in citations:
            href = citation["href"]
            try:
                uri = FrbrUri.parse(href)
                # is it a local reference?
                if uri.portion and uri.work_uri(False) == doc.work_frbr_uri:
                    href = f"#{uri.portion}"
            except ValueError:
                continue

            # wrap markdown-style links around cited text based on offset and length
            message.content = (
                message.content[: citation["start"]]
                + "["
                + citation["text"]
                + "]("
                + href
                + ")"
                + message.content[citation["end"] :]
            )
    return {}


def is_fresh_chat(state: DocumentChatState) -> bool:
    return not (state["messages"])


graph_builder = StateGraph(DocumentChatState)
graph_builder.add_node("initial_prompt", initial_prompt)
graph_builder.add_node("doc_metadata", doc_metadata)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("markup_refs", markup_refs)
graph_builder.add_node("tools", ToolNode(tools=ALL_TOOLS))

# when resuming a chat, jump to the chatbot state
graph_builder.add_conditional_edges(
    START, is_fresh_chat, {True: "initial_prompt", False: "chatbot"}
)
graph_builder.add_edge("initial_prompt", "doc_metadata")
graph_builder.add_edge("doc_metadata", "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", "markup_refs")
graph_builder.add_edge("markup_refs", END)


@asynccontextmanager
async def aget_chat_graph() -> AsyncIterator[CompiledStateGraph]:
    async with aget_graph_memory() as memory:
        yield graph_builder.compile(checkpointer=memory)


@contextmanager
def get_chat_graph(use_checkpointer=True) -> Iterator[CompiledStateGraph]:
    if use_checkpointer:
        with get_graph_memory() as memory:
            yield graph_builder.compile(checkpointer=memory)
    else:
        yield graph_builder.compile()


_db_setup = False


def get_db_url() -> str:
    db_config = settings.DATABASES["default"]
    return (
        f"postgresql://{db_config['USER']}:{db_config['PASSWORD']}"
        f"@{db_config['HOST']}:{db_config['PORT']}/{db_config['NAME']}"
    )


@asynccontextmanager
async def aget_graph_memory() -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(get_db_url()) as memory:
        global _db_setup
        if not _db_setup:
            await memory.setup()
            _db_setup = True
        yield memory


@contextmanager
def get_graph_memory() -> Iterator[AsyncPostgresSaver]:
    with PostgresSaver.from_conn_string(get_db_url()) as memory:
        global _db_setup
        if not _db_setup:
            memory.setup()
            _db_setup = True
        yield memory


def get_chat_config(thread) -> RunnableConfig:
    """Given a ChatThread object, get the config object to provide to langgraph."""
    return {
        "configurable": {
            "thread_id": str(thread.id),
            "document_id": thread.document_id,
            "user_id": thread.user_id,
        },
        "callbacks": [langfuse_callback],
    }


def get_message_snapshot(
    thread, message_id
) -> Tuple[AnyMessage | None, StateSnapshot | None]:
    """Get a (message, snapshot) tuple for the given message ID in the chat thread, or None if not found."""
    with get_chat_graph() as graph:
        history = graph.get_state_history(get_chat_config(thread))
        # this is ordered most recent first
        for snapshot in history:
            for message in reversed(snapshot.values.get("messages", [])):
                if message.id == message_id:
                    return message, snapshot

    return None, None


async def aget_previous_response(graph, config, message_id):
    """Get the AI response message that follows the given user message ID in the chat history."""
    found_user = False
    # this is ordered most recent first
    async for snapshot in graph.aget_state_history(config):
        for msg in snapshot.values.get("messages", []):
            if msg.id == message_id and msg.type == "human":
                found_user = True
            elif found_user and msg.type == "ai":
                return msg
