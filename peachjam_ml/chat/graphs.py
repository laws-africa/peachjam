from contextlib import contextmanager
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.models import User
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from peachjam.models import CoreDocument, Legislation
from peachjam_ml.chat.tools import (
    answer_document_question,
    get_provision_eid,
    get_provision_text,
    provision_commencement_info,
)


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


chat_llm = init_chat_model("openai:gpt-5-mini", temperature=0)
tools = [
    answer_document_question,
    get_provision_eid,
    provision_commencement_info,
    get_provision_text,
]
llm_with_tools = chat_llm.bind_tools(tools)


def chatbot(state: DocumentChatState):
    state["messages"].append(
        HumanMessage(
            content=state["user_message"]["content"], id=state["user_message"]["id"]
        )
    )
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


def initial_prompt(state: DocumentChatState):
    user = User.objects.get(pk=state["user_id"])
    app = settings.PEACHJAM["APP_NAME"]
    prompt = (
        f"You are a helpful assistant for the website {app}, which is a legal information database with judgments, "
        "legislation and gazettes. The user is asking you questions through a page on the website that is showing them "
        "a document. You must answer their questions about the document. "
        "Only use the document for answers; if the answer is not present, say so. "
        "The full document contents are not provided because they are very long. Instead, "
        "use one of the provided tools to answer questions about the document.\n\n"
        f"The user's name is: {user.get_full_name()}"
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
            + "; ".join(an.name for an in alternative_names)
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

    msg = (
        "Here is some information about the document to help answer questions:\n\n"
        + ("\n".join(metadata))
    )
    return {"messages": [SystemMessage(content=msg)]}


def is_fresh_chat(state: DocumentChatState) -> bool:
    return not (state["messages"])


graph_builder = StateGraph(DocumentChatState)
graph_builder.add_node("initial_prompt", initial_prompt)
graph_builder.add_node("doc_metadata", doc_metadata)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))

# when resuming a chat, jump to the chatbot state
graph_builder.add_conditional_edges(
    START, is_fresh_chat, {True: "initial_prompt", False: "chatbot"}
)
graph_builder.add_edge("initial_prompt", "doc_metadata")
graph_builder.add_edge("doc_metadata", "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)


@contextmanager
def get_chat_graph():
    with get_graph_memory() as memory:
        yield graph_builder.compile(checkpointer=memory)


_db_setup = False


@contextmanager
def get_graph_memory():
    db_config = settings.DATABASES["default"]
    db_url = (
        f"postgresql://{db_config['USER']}:{db_config['PASSWORD']}"
        f"@{db_config['HOST']}:{db_config['PORT']}/{db_config['NAME']}"
    )
    with PostgresSaver.from_conn_string(db_url) as memory:
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
            "document_id": thread.document.pk,
            "user_id": thread.user.pk,
        },
        "callbacks": [langfuse_callback],
    }


def get_message_snapshot(thread, message_id):
    """Get a (message, snapshot) tuple for the given message ID in the chat thread, or None if not found."""
    with get_chat_graph() as graph:
        history = graph.get_state_history(get_chat_config(thread))
        # this is ordered most recent first
        for snapshot in history:
            for message in reversed(snapshot.values.get("messages", [])):
                if message.id == message_id:
                    return message, snapshot

    return None, None
