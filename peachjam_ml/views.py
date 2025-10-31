import json

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView
from langchain_core.messages import HumanMessage

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam_ml.chat import get_system_prompt, graph, langfuse, langfuse_callback
from peachjam_ml.models import ChatThread, DocumentEmbedding
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


class StartDocumentChatView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = CoreDocument
    permission_required = "peachjam_ml.add_chatthread"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        document = self.get_object()

        if "new" in request.GET:
            # force a new thread
            thread = ChatThread.objects.create(
                document=document,
                user=self.request.user,
            )
        else:
            # get the latest thread, if any
            thread = (
                ChatThread.objects.filter(
                    user=self.request.user,
                    document=document,
                )
                .order_by("-created_at")
                .first()
            )

            if not thread:
                # create a new one (avoiding race conditions)
                thread, created = ChatThread.objects.get_or_create(
                    document=document,
                    user=self.request.user,
                )

        state = graph.get_state(get_chat_config(thread)).values
        return render_thread_state(thread, state)


class DocumentChatView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ChatThread
    permission_required = "peachjam_ml.add_chatthread"
    http_method_names = ["post"]

    def get_queryset(self):
        return ChatThread.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        thread = self.get_object()

        # parse json input from request body
        input = json.loads(request.body)
        config = get_chat_config(thread)
        snapshot = graph.get_state(config)

        if not snapshot.values:
            state = {
                "messages": [get_system_prompt(thread.user)],
                "user_id": thread.user.pk,
                "document_id": thread.document.pk,
            }
        else:
            state = snapshot.values

        message = input.get("message", "")
        message = HumanMessage(message["content"], id=message["id"])
        state["messages"].append(message)

        with langfuse.start_as_current_observation(
            name="document_chat",
            as_type="generation",
            input={"expression_frbr_uri": thread.document.expression_frbr_uri},
        ) as generation:
            result = graph.invoke(
                state,
                config,
            )
            # todo link generation.trace id to messages?
            generation.update_trace(
                user_id=thread.user.username, session_id=str(thread.id)
            )

        return render_thread_state(thread, result)


def get_chat_config(thread):
    return {
        "configurable": {
            "thread_id": str(thread.id),
            "document_id": thread.document.pk,
            "user_id": thread.user.pk,
        },
        "callbacks": [langfuse_callback],
    }


def render_thread_state(thread, state):
    def serialise(message):
        return {
            "id": message.id,
            "role": message.type,
            "content": message.content,
        }

    return JsonResponse(
        {
            "thread_id": str(thread.id),
            "messages": [
                serialise(m)
                for m in state.get("messages", [])
                # other types are system and tool
                if m.type in ["ai", "human"]
            ],
        }
    )
