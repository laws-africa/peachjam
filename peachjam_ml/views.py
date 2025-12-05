import json

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F
from django.http.response import HttpResponse, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView

from peachjam.helpers import add_slash_to_frbr_uri
from peachjam.models import CoreDocument, Folder
from peachjam.views.documents import DocumentDetailView
from peachjam.views.mixins import AsyncDispatchMixin
from peachjam_ml.chat.graphs import (
    aget_chat_graph,
    aget_previous_response,
    get_chat_config,
    get_chat_graph,
    get_message_snapshot,
    langfuse,
)
from peachjam_ml.models import ChatThread, DocumentEmbedding
from peachjam_subs.mixins import SubscriptionRequiredMixin
from peachjam_subs.models import Subscription


@method_decorator(add_slash_to_frbr_uri(), name="setup")
@method_decorator(never_cache, name="dispatch")
class SimilarDocumentsDocumentDetailView(SubscriptionRequiredMixin, DetailView):
    permission_required = "peachjam_ml.view_documentembedding"
    template_name = "peachjam/document/_similar_documents.html"
    subscription_required_template = template_name
    slug_url_kwarg = "frbr_uri"
    slug_field = "expression_frbr_uri"
    model = CoreDocument

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
    subscription_required_template = template_name
    model = Folder

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
    LoginRequiredMixin, SubscriptionRequiredMixin, DocumentDetailView
):
    """Starts a new chat thread for a document, or returns an existing one.

    Enforces permissions and limits as follows, returning a 403 with HTML to display to the user explaining
    what they can do to gain access:

    1. add_chatthread permission: user must create an account or upgrade their subscription
    2. monthly unique document chat limit: user must upgrade their subscription or wait until next month
    """

    slug_field = "pk"
    slug_url_kwarg = "pk"
    permission_required = "peachjam_ml.add_chatthread"
    http_method_names = ["get", "post"]
    subscription_required_status = 403
    subscription_required_template = "peachjam_ml/_chat_permission_denied.html"

    def get(self, request, *args, **kwargs):
        document = self.get_object()

        thread = (
            ChatThread.objects.filter(user=self.request.user, document=document)
            .order_by("-created_at")
            .first()
        )
        if thread:
            return self.build_thread_response(thread)

        return HttpResponse(status=404)

    def post(self, request, *args, **kwargs):
        document = self.get_object()

        if limit_response := self.check_limits(document):
            return limit_response

        thread = ChatThread.objects.create(
            document=document,
            user=self.request.user,
        )

        return self.build_thread_response(thread)

    def build_thread_response(self, thread):
        with get_chat_graph() as graph:
            state = graph.get_state(get_chat_config(thread)).values

        return JsonResponse(
            {
                "thread_id": str(thread.id),
                "messages": [
                    serialise_message(m)
                    for m in state.get("messages", [])
                    if m.type in ["ai", "human"]
                ],
            }
        )

    def check_limits(self, document):
        n_active = ChatThread.count_active_for_user(self.request.user)
        sub = Subscription.get_or_create_active_for_user(self.request.user)

        limit_reached, lowest_product = sub.get_feature_limit_status(
            "document_chat_limit", n_active
        )
        if limit_reached:
            context = self.build_subscription_required_context(
                limit_reached=True,
                chat_limit=sub.product_offering.product.document_chat_limit,
                lowest_product=lowest_product,
            )
            return self.render_subscription_required(context)

        return None

    def render_subscription_required(self, context):
        html = render_to_string(
            self.get_subscription_required_template(),
            context,
            request=self.request,
        )
        return JsonResponse({"message_html": html}, status=403)


class ChatThreadDetailMixin(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ChatThread
    permission_required = "peachjam_ml.add_chatthread"

    def get_queryset(self):
        return (
            ChatThread.objects.filter(user=self.request.user)
            .select_related("document", "user")
            .defer(
                "document__content_html",
                "document__toc_json",
                "document__metadata_json",
            )
        )


class DocumentChatView(AsyncDispatchMixin, ChatThreadDetailMixin):
    """Streams a response to a chat message."""

    http_method_names = ["get"]

    async def get(self, request, *args, **kwargs):
        thread = await sync_to_async(self.get_object)()

        content = (request.GET.get("c") or "").strip()
        msg_id = (request.GET.get("id") or "").strip()
        if not content:
            return HttpResponse(status=400)
        message = {"content": content, "id": msg_id}

        response = StreamingHttpResponse(
            self.stream(thread, message), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # disable Nginx buffering

        return response

    async def stream(self, thread, message):
        async with aget_chat_graph() as graph:
            config = get_chat_config(thread)
            snapshot = await graph.aget_state(config)
            if not snapshot.values:
                # setup initial state
                state = {
                    "user_id": thread.user_id,
                    "document_id": thread.document_id,
                }
            else:
                state = snapshot.values
            state["user_message"] = message

            # if the user has already sent this query; find the first AI message after it, and return that
            reply = await aget_previous_response(graph, config, message["id"])
            if reply:
                yield self.format_sse("message", serialise_message(reply))
                return

            with langfuse.start_as_current_observation(
                name="document_chat",
                as_type="generation",
                input={
                    "expression_frbr_uri": thread.document.expression_frbr_uri,
                    "question": message["content"],
                },
            ) as generation:
                config["configurable"]["trace_id"] = generation.trace_id
                async for chunk, metadata in graph.astream(
                    state,
                    config,
                    stream_mode="messages",
                    # checkpoint only once a whole call is complete, to avoid saving partial state
                    # alternatively, we need to run through the messages when "resuming" and ensure that any
                    # dangling (unanswered) tool calls are removed
                    durability="exit",
                ):
                    if (
                        chunk.type == "AIMessageChunk"
                        # TODO: make chatbot node type configurable
                        and metadata.get("langgraph_node") == "chatbot"
                        and chunk.content
                    ):
                        yield self.format_sse(
                            "chunk", {"id": chunk.id, "c": chunk.content}
                        )

                # get final response message
                result = (await graph.aget_state(config)).values
                reply = result.get("messages", [])[-1]
                generation.update_trace(
                    tags=[settings.PEACHJAM["APP_NAME"]],
                    user_id=thread.user.username,
                    session_id=str(thread.id),
                    output={"reply": reply.content},
                )

            # send the full final response
            yield self.format_sse("message", serialise_message(reply))
            yield self.format_sse("done", {})

            await thread.asave_message_history(graph, config)

    def format_sse(self, event, data):
        return f"event: {event}\n" + f"data: {json.dumps(data)}\n\n"


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


def serialise_message(message):
    return {
        "id": message.id,
        "role": message.type,
        "content": message.content,
    }
