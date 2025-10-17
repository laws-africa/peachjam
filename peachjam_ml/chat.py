from typing import Annotated, List

from django.conf import settings
from langchain.chat_models import init_chat_model
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from peachjam.analysis.citations import CitatorMatcher
from peachjam.models import CoreDocument, Legislation
from peachjam.xmlutils import parse_html_str


class DocumentChatState(TypedDict):
    document_id: int
    user_id: int
    messages: Annotated[List[BaseMessage], add_messages]


@tool
def answer_document_question(config: RunnableConfig, question: str) -> str:
    """Answers a question about the content of the document. It has no memory of previous questions."""
    doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])
    text = doc.get_content_as_text()

    response = llm.invoke(
        [
            SystemMessage(
                content="You are a question answering tool. Only use the document for answers; if you cannot answer "
                "the question based on the document content, say so."
            ),
            HumanMessage(content="The document content is below:\n\n" + text),
            HumanMessage(content=question),
        ]
    )

    return response.content


@tool
def get_provision_eid(config: RunnableConfig, provision: str) -> str:
    """Tries to find the unique internal EID of a provision of a document, which can be used to find out additional
     information about the provision. The provision must be stated similar to the following:

    - section 32
    - section 5(2)(a)
    - chapter 5
    - paragraph 4
    """
    doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])

    # TODO: this should be way easier :(
    resp = CitatorMatcher().call_citator(
        {
            "frbr_uri": doc.expression_frbr_uri,
            "format": "html",
            "body": f'<p>{provision} of <a href="{doc.expression_frbr_uri}" id="fake">xx</a></p>',
        }
    )

    root = parse_html_str(resp["body"])
    # grab the first a element without an id
    for a in root.xpath("//a[not(@id)]"):
        href = a.get("href", "")
        if "~" in href:
            eid = href.split("~")[-1]
            return f"The EID of provision '{provision}' is: {eid}"

    return f"Provision '{provision}' could not be identified."


@tool
def get_provision_text(config: RunnableConfig, eid: str) -> str:
    """Returns the text of a provision given its EID."""
    doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])
    provision_html = doc.get_provision_by_eid(eid)
    if not provision_html:
        return "No provision found with that EID."

    root = parse_html_str(provision_html)
    text = " ".join(root.itertext())

    return f"The text of provision with EID {eid} is:\n\n{text}"


@tool
def provision_commencement_info(config: RunnableConfig, eid: str) -> str:
    """Provides information about the commencement status of a provision given its EID."""
    doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])
    # TODO: don't allow this tool for non-legislation documents
    if not isinstance(doc, Legislation):
        return "This tool can only be used for legislation documents."

    if not doc.commenced:
        return "This legislation has not yet commenced, and so the provision has not commenced either."

    for event in doc.commencements_json or []:
        if event["all_provisions"]:
            return (
                f"The provision commenced at the same time as all other provisions, on {event['date']} "
                f"by '{event['commencing_title']}'."
            )
        if eid in event.get("provisions", []):
            return f"The provision commenced on {event['date']} by '{event['commencing_title']}'."

    return "That provision has not commenced."


llm = init_chat_model("openai:gpt-4.1", temperature=0)
tools = [
    answer_document_question,
    get_provision_eid,
    provision_commencement_info,
    get_provision_text,
]
llm_with_tools = llm.bind_tools(tools)
langfuse_callback = CallbackHandler()

# Langfuse uses environment variables to configure itself
# we block elasticsearch-api instrumentation which comes through from the opentelemetry data
langfuse = Langfuse(blocked_instrumentation_scopes=["elasticsearch-api"])


def chatbot(state: DocumentChatState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


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


graph_builder = StateGraph(DocumentChatState)
graph_builder.add_node("doc_metadata", doc_metadata)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))

graph_builder.add_edge(START, "doc_metadata")
graph_builder.add_edge("doc_metadata", "chatbot")
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

memory = InMemorySaver()
graph = graph_builder.compile(checkpointer=memory)


def get_system_prompt(user) -> SystemMessage:
    app = settings.PEACHJAM["APP_NAME"]

    system_prompt = (
        f"You are a helpful assistant for the website {app}, which is a legal information database with judgments, "
        "legislation and gazettes. The user is asking you questions through a page on the website that is showing them "
        "a document. You must answer their questions about the document. "
        "Only use the document for answers; if the answer is not present, say so. "
        "The full document contents are not provided because they are very long. Instead, "
        "use one of the provided tools to answer questions about the document.\n\n"
        f"The user's name is: {user.get_full_name()}"
    )

    return SystemMessage(content=system_prompt)
