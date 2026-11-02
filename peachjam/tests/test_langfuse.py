"""Verify observation contracts using the real SDK without network access."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from django.conf import settings
from django.test import SimpleTestCase
from langfuse import Langfuse
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from peachjam.analysis.summariser import JudgmentSummariser
from peachjam.langfuse import should_export_span
from peachjam.views.chat import DocumentChatView


class LangfuseObservationTest(SimpleTestCase):
    def setUp(self):
        self.requests = []

        def respond(request):
            self.requests.append(request)
            return httpx.Response(202, json={"message": "Accepted"})

        http_client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(http_client.close)
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider(
            resource=Resource.create(
                {"langfuse.environment": "test", "langfuse.release": "test-release"}
            )
        )
        self.client = Langfuse(
            public_key=f"test-{uuid4()}",
            secret_key="test-secret",
            tracer_provider=self.provider,
            span_exporter=self.exporter,
            environment="test",
            release="test-release",
            should_export_span=should_export_span,
            httpx_client=http_client,
        )
        self.addCleanup(self.client.shutdown)
        self.tracer = self.provider.get_tracer(
            "openinference.instrumentation.openai_agents"
        )

    def spans(self):
        self.client.flush()
        return {span.name: span for span in self.exporter.get_finished_spans()}

    def assert_hierarchy(self, root, child):
        self.assertEqual(child.parent.span_id, root.context.span_id)
        self.assertEqual(child.context.trace_id, root.context.trace_id)
        for span in (root, child):
            self.assertEqual(span.resource.attributes["langfuse.environment"], "test")
            self.assertEqual(
                span.resource.attributes["langfuse.release"], "test-release"
            )
            self.assertEqual(
                span.attributes["langfuse.trace.tags"], (settings.PEACHJAM["APP_NAME"],)
            )
            self.assertNotIn("langfuse.trace.public", span.attributes)

    async def test_chat_propagates_to_children_and_keeps_root_io(self):
        thread = SimpleNamespace(
            id=uuid4(),
            user=SimpleNamespace(username="reader"),
            document=SimpleNamespace(expression_frbr_uri="/akn/za/judgment/2026/1"),
            get_thread_messages=lambda: [],
            asave_message_history=AsyncMock(),
        )
        chat = MagicMock(setup=AsyncMock())
        chat.markup_refs.return_value = "Rendered reply"

        async def events():
            with self.tracer.start_as_current_span("model-generation") as span:
                span.set_attribute("gen_ai.usage.input_tokens", 12)
                span.set_attribute("gen_ai.usage.output_tokens", 4)
            if False:
                yield

        result = SimpleNamespace(stream_events=events)
        with (
            patch("peachjam.views.chat.langfuse", self.client),
            patch("peachjam.views.chat.DocumentChat", return_value=chat),
            patch("peachjam.views.chat.Runner.run_streamed", return_value=result),
            patch(
                "peachjam.views.chat.extract_assistant_response",
                return_value={"role": "ai", "content": "Reply"},
            ),
        ):
            messages = [
                item
                async for item in DocumentChatView().stream(
                    thread, {"content": "Question", "id": "message-1"}
                )
            ]

        spans = self.spans()
        root, child = spans["document_chat"], spans["model-generation"]
        self.assert_hierarchy(root, child)
        for span in (root, child):
            self.assertEqual(span.attributes["user.id"], "reader")
            self.assertEqual(span.attributes["session.id"], str(thread.id))
            self.assertEqual(span.attributes["langfuse.trace.name"], "document_chat")
        self.assertEqual(
            json.loads(root.attributes["langfuse.observation.input"])["question"],
            "Question",
        )
        self.assertEqual(
            json.loads(root.attributes["langfuse.observation.output"]),
            {"reply": "Rendered reply"},
        )
        self.assertIn(format(root.context.trace_id, "032x"), messages[0])
        thread.asave_message_history.assert_awaited_once()

    def test_summary_keeps_source_and_result_on_root(self):
        summary = MagicMock()
        summary.model_dump.return_value = {"summary": "Result"}
        summariser = JudgmentSummariser.__new__(JudgmentSummariser)
        summariser.summary_prompt = None

        def generate(text):
            with self.tracer.start_as_current_span("summary-generation"):
                return summary

        with (
            patch("peachjam.analysis.summariser.langfuse", self.client),
            patch.object(summariser, "generate_summary", side_effect=generate),
            patch.object(summariser, "match_flynotes", side_effect=lambda value: value),
            patch.object(
                summariser,
                "translate_summary",
                side_effect=lambda value, language: value,
            ),
            patch.object(
                summariser, "normalise_summary", side_effect=lambda value: value
            ),
        ):
            self.assertIs(
                summariser.summarise("/akn/za/judgment/2026/1", "Judgment text"),
                summary,
            )

        spans = self.spans()
        root = spans["summarise_judgment"]
        self.assert_hierarchy(root, spans["summary-generation"])
        self.assertEqual(
            json.loads(root.attributes["langfuse.observation.input"]),
            {"expression_frbr_uri": "/akn/za/judgment/2026/1", "text": "Judgment text"},
        )
        self.assertEqual(
            json.loads(root.attributes["langfuse.observation.output"]),
            {"summary": "Result"},
        )

    def test_export_policy_uses_defaults_and_blocks_elasticsearch(self):
        for scope in ("elasticsearch-api", "tool-internals"):
            with self.provider.get_tracer(scope).start_as_current_span(scope) as span:
                if scope == "elasticsearch-api":
                    # The exclusion must win even when the default filter accepts it.
                    span.set_attribute("gen_ai.operation.name", "chat")
        spans = self.spans()
        self.assertNotIn("elasticsearch-api", spans)
        self.assertNotIn("tool-internals", spans)

    def test_vote_score_flushes_to_current_scores_api(self):
        trace_id = "1" * 32
        self.client.create_score(
            trace_id=trace_id, name="user-vote", value=1, data_type="NUMERIC"
        )
        self.client.flush()
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url.path, "/api/public/scores")
        score = json.loads(request.content)[0]
        self.assertEqual(score["traceId"], trace_id)
        self.assertEqual(score["name"], "user-vote")
        self.assertEqual(score["value"], 1)
