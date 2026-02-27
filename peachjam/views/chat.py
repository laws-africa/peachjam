import json

from agents import Runner
from agents.stream_events import RawResponsesStreamEvent
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import F
from django.http.response import HttpResponse, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.views.generic import DetailView
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent

from peachjam.chat.agent import DocumentChat, extract_assistant_response, langfuse
from peachjam.models import DocumentChatThread
from peachjam.views.documents import DocumentDetailView
from peachjam.views.mixins import AsyncDispatchMixin
from peachjam_subs.mixins import SubscriptionRequiredMixin
from peachjam_subs.models import Product, Subscription


class StartDocumentChatView(
    LoginRequiredMixin, SubscriptionRequiredMixin, DocumentDetailView
):
    """Starts a new chat thread for a document, or returns an existing one.

    Enforces permissions and limits as follows, returning a 403 with HTML to display to the user explaining
    what they can do to gain access:

    1. add_documentchatthread permission: user must create an account or upgrade their subscription
    2. monthly unique document chat limit: user must upgrade their subscription or wait until next month
    """

    slug_field = "pk"
    slug_url_kwarg = "pk"
    permission_required = "peachjam.add_documentchatthread"
    http_method_names = ["get", "post"]
    subscription_required_status = 403
    subscription_required_template = "peachjam/chat/_chat_permission_denied.html"

    def get(self, request, *args, **kwargs):
        document = self.get_object()

        thread = (
            DocumentChatThread.objects.filter(
                user=self.request.user, core_document=document
            )
            .order_by("-created_at")
            .first()
        )
        if thread:
            return self.build_thread_response(thread)

        # return usage limit info even if no thread, to inform the user of their limits before they start a chat
        return JsonResponse(
            {
                "thread_id": "",
                "messages": [],
                "usage_limit_html": self.build_usage_limit_html(),
            },
            status=404,
        )

    def post(self, request, *args, **kwargs):
        document = self.get_object()

        if limit_response := self.check_limits(document):
            return limit_response

        thread = DocumentChatThread.objects.create(
            core_document=document,
            user=self.request.user,
        )

        return self.build_thread_response(thread)

    def build_thread_response(self, thread):
        return JsonResponse(
            {
                "thread_id": str(thread.id),
                "messages": thread.get_thread_messages(),
                "usage_limit_html": self.build_usage_limit_html(),
            }
        )

    def build_usage_limit_html(self):
        n_active = DocumentChatThread.count_active_for_user(self.request.user)
        sub = Subscription.get_or_create_active_for_user(self.request.user)
        chat_limit = sub.product_offering.product.document_chat_limit
        if not chat_limit or chat_limit >= 999999:
            return None

        lowest_product = Product.get_user_upgrade_products(
            self.request.user,
            feature="document_chat_limit",
            count=chat_limit,
        ).first()
        if not lowest_product:
            return None

        context = {
            "chats_used": n_active,
            "chat_limit": chat_limit,
            "lowest_product": lowest_product,
        }

        return render_to_string(
            "peachjam/chat/_chat_usage_limit.html",
            context,
            request=self.request,
        )

    def check_limits(self, document):
        n_active = DocumentChatThread.count_active_for_user(self.request.user)
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
        return JsonResponse(
            {"message_html": html, "limit_reached": context.get("limit_reached")},
            status=403,
        )


class ChatThreadDetailMixin(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = DocumentChatThread
    permission_required = "peachjam.add_documentchatthread"

    def get_queryset(self):
        return DocumentChatThread.objects.filter(user=self.request.user).select_related(
            "user"
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # ensure the real document is loaded
        obj.document
        return obj


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
        chat = DocumentChat(thread)
        await chat.setup()

        with langfuse.start_as_current_observation(
            name="document_chat",
            as_type="generation",
            input={
                "expression_frbr_uri": thread.document.expression_frbr_uri,
                "question": message["content"],
            },
        ) as generation:
            result = Runner.run_streamed(
                chat.agent,
                input=message["content"],
                context=chat.context,
                session=chat.session,
            )
            async for event in result.stream_events():
                if isinstance(event, RawResponsesStreamEvent) and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    if event.data.delta:
                        yield self.format_sse(
                            "chunk",
                            {"id": event.data.item_id, "c": event.data.delta},
                        )

            reply = extract_assistant_response(result)
            reply["content"] = await sync_to_async(chat.markup_refs)(reply["content"])
            reply["trace_id"] = generation.trace_id

            generation.update_trace(
                tags=[settings.PEACHJAM["APP_NAME"]],
                user_id=thread.user.username,
                session_id=str(thread.id),
                output={"reply": reply["content"]},
            )

        # send the full final response
        yield self.format_sse("message", serialise_message(reply))
        yield self.format_sse("done", {})

        messages = thread.get_thread_messages()
        messages.append(
            {
                "id": message["id"],
                "role": "human",
                "content": message["content"],
            }
        )
        messages.append(reply)
        await thread.asave_message_history(messages)

    def format_sse(self, event, data):
        return f"event: {event}\n" + f"data: {json.dumps(data)}\n\n"


class VoteChatMessageView(ChatThreadDetailMixin):
    """View to handle upvoting or downvoting an AI-provided chat message."""

    http_method_names = ["post"]
    up = True

    def post(self, request, pk, message_id, *args, **kwargs):
        thread = self.get_object()
        message = thread.get_message_by_id(message_id)
        if message and message.get("role") == "ai":
            # store locally
            increment = 1 if self.up else -1
            DocumentChatThread.objects.filter(pk=thread.pk).update(
                score=F("score") + increment
            )

            # push to Langfuse
            trace_id = message.get("trace_id")
            if trace_id:
                langfuse.create_score(
                    trace_id=trace_id,
                    name="user-vote",
                    value=1 if self.up else -1,
                    data_type="NUMERIC",
                )

        return HttpResponse(status=200)


def serialise_message(message):
    if isinstance(message, dict):
        return message

    return {
        "id": message.id,
        "role": message.type,
        "content": message.content,
    }
