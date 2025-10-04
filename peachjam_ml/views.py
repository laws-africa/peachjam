import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView
from langchain_core.messages import HumanMessage, SystemMessage

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam_ml.chat import graph
from peachjam_ml.models import DocumentEmbedding
from peachjam_subs.mixins import SubscriptionRequiredMixin


@method_decorator(add_slash_to_frbr_uri(), name="setup")
@method_decorator(never_cache, name="dispatch")
class SimilarDocumentsDocumentDetailView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/document/_similar_documents.html"
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument

    def get_subscription_required_template(self):
        return self.template_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # get the similar documents, best first
        similar_documents = DocumentEmbedding.get_similar_documents([self.object.pk])
        # get the actual documents
        docs = {
            d.id: d
            for d in CoreDocument.objects.filter(
                pk__in=[sd["document_id"] for sd in similar_documents]
            )
        }
        # preserve ordering
        context["similar_documents"] = [
            docs.get(sd["document_id"]) for sd in similar_documents
        ]
        return context


class SimilarDocumentsFolderView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/_similar_documents_folder.html"
    model = Folder

    def get_subscription_required_template(self):
        return self.template_name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc_ids = self.object.saved_documents.values_list("document_id", flat=True)
        context["similar_documents"] = DocumentEmbedding.get_similar_documents(doc_ids)
        return context


class DocumentChatView(LoginRequiredMixin, DetailView):
    # TODO: perms
    model = CoreDocument

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # TODO: return existing chat messages or create a new one

        config = {"configurable": {"thread_id": "1"}}
        snapshot = graph.get_state(config)
        return self.render_state(snapshot.values)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # parse json input from request body
        input = json.loads(request.body)

        # TODO: make thread_id dynamic
        config = {"configurable": {"thread_id": "1"}}
        snapshot = graph.get_state(config)

        messages = []
        if not snapshot.values:
            document_text = self.object.get_content_as_text()[:1000]
            system_prompt = (
                "You are a helpful assistant that answers questions about the provided document. "
                "Only use the document for answers; if the answer is not present, say so.\n\n"
                f"Document contents:\n{document_text}"
            )
            system_message = SystemMessage(content=system_prompt)
            messages.append(system_message)

        message = input.get("message", "")
        message = HumanMessage(message["content"], id=message["id"])
        messages.append(message)

        result = graph.invoke(
            {"messages": messages},
            config,
        )

        return self.render_state(result)

    def render_state(self, result):
        return JsonResponse(
            {
                "messages": [
                    serialise(m)
                    for m in result.get("messages", [])
                    if m.type != "system"
                ]
            }
        )


def serialise(message):
    return {
        "id": message.id,
        "role": message.type,
        "content": message.content,
    }
