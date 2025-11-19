import json

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F
from django.http.response import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView
from rest_framework.exceptions import ValidationError

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam.views.documents import DocumentDetailView
from peachjam_ml.chat.graphs import (
    get_chat_config,
    get_chat_graph,
    get_message_snapshot,
    langfuse,
)
from peachjam_ml.models import ChatThread, DocumentEmbedding
from peachjam_ml.serializers import ChatRequestSerializer
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
        work_ids = self.object.saved_documents.values_list("work_id", flat=True)
        doc_ids = (
            CoreDocument.objects.filter(work_id__in=work_ids)
            .latest_expression()
            .values_list("id", flat=True)
        )
        context["similar_documents"] = DocumentEmbedding.get_similar_documents(doc_ids)
        return context


class StartDocumentChatView(
    LoginRequiredMixin, PermissionRequiredMixin, DocumentDetailView
):
    slug_field = "pk"
    slug_url_kwarg = "pk"
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

        with get_chat_graph() as graph:
            state = graph.get_state(get_chat_config(thread)).values
        return render_thread_state(thread, state)


class ChatThreadDetailMixin(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ChatThread
    permission_required = "peachjam_ml.add_chatthread"

    def get_queryset(self):
        return ChatThread.objects.filter(user=self.request.user)


class DocumentChatView(ChatThreadDetailMixin):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        thread = self.get_object()

        # validate request
        input = json.loads(request.body)
        serializer = ChatRequestSerializer(data=input.get("message", {}))
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return JsonResponse({"errors": e.detail}, status=400)
        message = serializer.data

        config = get_chat_config(thread)
        with get_chat_graph() as graph:
            snapshot = graph.get_state(config)

            if not snapshot.values:
                state = {
                    "user_id": thread.user.pk,
                    "document_id": thread.document.pk,
                }
            else:
                state = snapshot.values

            state["user_message"] = message

            with langfuse.start_as_current_observation(
                name="document_chat",
                as_type="generation",
                input={
                    "expression_frbr_uri": thread.document.expression_frbr_uri,
                    "question": message["content"],
                },
            ) as generation:
                config["configurable"]["trace_id"] = generation.trace_id
                result = graph.invoke(
                    state,
                    config,
                    # checkpoint only once a whole call is complete, to avoid saving partial state
                    # alternatively, we need to run through the messages when "resuming" and ensure that any
                    # dangling (unanswered) tool calls are removed
                    durability="exit",
                )
                generation.update_trace(
                    user_id=thread.user.username,
                    session_id=str(thread.id),
                    output={"reply": result.get("messages", [])[-1].content},
                )

            history = graph.get_state_history(config)
            thread.messages_json = self.serialise_message_history(history)
            thread.save()

        return render_thread_state(thread, result)

    def serialise_message_history(self, history):
        # we just want the messages from the first snapshot
        for snapshot in history:
            return [
                message.to_json() for message in snapshot.values.get("messages", [])
            ]


class VoteChatMessageView(ChatThreadDetailMixin):
    """View to handle upvoting or downvoting an AI-provided chat message."""

    http_method_names = ["post"]
    up = True

    def post(self, request, pk, message_id, *args, **kwargs):
        thread = self.get_object()
        message, snapshot = get_message_snapshot(thread, message_id)
        if message and message.type == "ai":
            # store locally
            increment = 1 if self.up else -1
            ChatThread.objects.filter(pk=thread.pk).update(score=F("score") + increment)

            # push to Langfuse
            trace_id = None
            if snapshot and snapshot.metadata:
                trace_id = snapshot.metadata.get("trace_id")
            if trace_id:
                langfuse.create_score(
                    trace_id=trace_id,
                    name="user-vote",
                    value=1 if self.up else -1,
                    data_type="NUMERIC",
                )

        return HttpResponse(status=200)


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
