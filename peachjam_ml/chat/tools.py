from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from peachjam.analysis.citations import CitatorMatcher
from peachjam.models import CoreDocument, Legislation
from peachjam.xmlutils import parse_html_str


@tool
def answer_document_question(config: RunnableConfig, question: str) -> str:
    """Answers a question about the content of the document. It has no memory of previous questions."""
    from .graphs import chat_llm

    doc = CoreDocument.objects.get(pk=config["configurable"]["document_id"])
    text = doc.get_content_as_text()

    response = chat_llm.invoke(
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
