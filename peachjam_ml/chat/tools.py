import requests
from asgiref.sync import sync_to_async
from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from peachjam.models import CoreDocument, Legislation
from peachjam.xmlutils import parse_html_str


@tool
async def answer_document_question(config: RunnableConfig, question: str) -> str:
    """Answers a question about the content of the current document. It knows which document is active.
    It has no memory of previous questions. Only use it if you need to answer a specific question about the document
    content. The document does not contain information about this website or its features."""
    from .graphs import chat_llm

    @sync_to_async
    def get_text():
        doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])
        return doc.get_content_as_text()

    text = await get_text()
    if len(text) > 1_250_000:
        return "Document text is too long to process."

    response = await chat_llm.ainvoke(
        [
            SystemMessage(
                content="You are a question answering tool. Only use the document content for answers; if you cannot"
                " answer the question based on the document content, say so."
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
    resp = get_citator_citations(doc.expression_frbr_uri, provision)

    # grab the first ref
    for ref in resp["citations"]:
        if ref["href"] and "~" in ref["href"]:
            eid = ref["href"].split("~")[-1]
            return f"The EID of provision '{provision}' is: {eid}"

    return f"Provision '{provision}' could not be identified."


def get_citator_citations(expression_frbr_uri, text):
    citator_url = settings.PEACHJAM["CITATOR_API"]
    citator_key = settings.PEACHJAM["LAWSAFRICA_API_KEY"]
    resp = requests.post(
        citator_url + "get-citations",
        json={
            "frbr_uri": expression_frbr_uri,
            "format": "text",
            "body": text,
        },
        headers={"Authorization": f"token {citator_key}"},
        timeout=60 * 10,
    )
    resp.raise_for_status()
    return resp.json()


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


def get_tools_for_document(document):
    tools = [
        answer_document_question,
    ]

    if isinstance(document, Legislation):
        tools.extend(
            [
                get_provision_eid,
                provision_commencement_info,
                get_provision_text,
            ]
        )

    return tools


ALL_TOOLS = [
    answer_document_question,
    get_provision_eid,
    get_provision_text,
    provision_commencement_info,
]
