import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import StateSnapshot

from peachjam.models import CoreDocument
from peachjam_ml.models import ChatThread


class DummyObservation:
    def __init__(self, trace_id="trace-id"):
        self.trace_id = trace_id
        self.updated = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update_trace(self, **kwargs):
        self.updated = kwargs


class DummyLangfuse:
    def __init__(self):
        self.observations = []
        self.scores = []

    def start_as_current_observation(self, *args, **kwargs):
        observation = DummyObservation()
        self.observations.append((args, kwargs, observation))
        return observation

    def create_score(self, **kwargs):
        self.scores.append(kwargs)


class DummyGraph:
    def __init__(self, result, history, initial_snapshot=None):
        self._result = result
        self._history = history
        self._initial_snapshot = initial_snapshot or StateSnapshot(
            values={},
            next=(),
            config={},
            metadata=None,
            created_at=None,
            parent_config=None,
            tasks=(),
            interrupts=(),
        )

    def get_state(self, config):
        return self._initial_snapshot

    def invoke(self, state, config):
        self.invoked_with = (state, config)
        return self._result

    def get_state_history(self, config):
        return self._history


class DocumentChatViewTests(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def setUp(self):
        self.user = User.objects.create_user(username="test", password="pwd")
        permission = Permission.objects.get(codename="add_chatthread")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)
        self.document = CoreDocument.objects.first()
        self.thread = ChatThread.objects.create(user=self.user, document=self.document)

    def test_document_chat_persists_state_history(self):
        human_message = HumanMessage(content="Hello", id="human-1")
        ai_message = AIMessage(content="Hi there", id="ai-1")
        result = {"messages": [human_message, ai_message]}
        history = [
            StateSnapshot(
                values={
                    "messages": [human_message, ai_message],
                    "user_id": self.user.pk,
                    "document_id": self.document.pk,
                },
                next=(),
                config={"configurable": {"thread_id": str(self.thread.id)}},
                metadata=None,
                created_at="2024-01-01T00:00:00Z",
                parent_config=None,
                tasks=(),
                interrupts=(),
            ),
            StateSnapshot(
                values={
                    "messages": [human_message],
                    "user_id": self.user.pk,
                    "document_id": self.document.pk,
                },
                next=(),
                config={"configurable": {"thread_id": str(self.thread.id)}},
                metadata=None,
                created_at="2023-12-31T23:00:00Z",
                parent_config=None,
                tasks=(),
                interrupts=(),
            ),
        ]
        dummy_graph = DummyGraph(result=result, history=history)

        dummy_langfuse = DummyLangfuse()

        @contextmanager
        def fake_graph():
            yield dummy_graph

        payload = {"message": {"id": "human-1", "content": "Hello"}}

        with mock.patch("peachjam_ml.views.get_chat_graph", fake_graph), mock.patch(
            "peachjam_ml.views.langfuse", dummy_langfuse
        ):
            response = self.client.post(
                f"/api/chats/{self.thread.pk}",
                data=json.dumps(payload),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.thread.refresh_from_db()
        self.assertEqual(len(self.thread.state_json), 1)
        state_entry = self.thread.state_json[0]
        self.assertEqual(state_entry["created_at"], "2024-01-01T00:00:00Z")
        self.assertEqual(state_entry["values"]["messages"][0]["kwargs"]["id"], "human-1")
        self.assertEqual(state_entry["values"]["messages"][1]["kwargs"]["id"], "ai-1")


class VoteChatMessageViewTests(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def setUp(self):
        self.user = User.objects.create_user(username="voter", password="pwd")
        permission = Permission.objects.get(codename="add_chatthread")
        self.user.user_permissions.add(permission)
        self.client.force_login(self.user)
        self.document = CoreDocument.objects.first()

    def test_vote_up_increments_thread_score(self):
        thread = ChatThread.objects.create(user=self.user, document=self.document)
        dummy_langfuse = DummyLangfuse()

        with mock.patch(
            "peachjam_ml.views.get_message_snapshot",
            return_value=(SimpleNamespace(type="ai"), SimpleNamespace(metadata={"trace_id": "trace"})),
        ), mock.patch("peachjam_ml.views.langfuse", dummy_langfuse):
            response = self.client.post(f"/api/chats/{thread.pk}/messages/ai-1/vote-up")

        self.assertEqual(response.status_code, 200)
        thread.refresh_from_db()
        self.assertEqual(thread.score, 1)
        self.assertEqual(len(dummy_langfuse.scores), 1)
        self.assertEqual(dummy_langfuse.scores[0]["value"], 1)

    def test_vote_down_decrements_thread_score_without_trace(self):
        thread = ChatThread.objects.create(user=self.user, document=self.document, score=2)
        dummy_langfuse = DummyLangfuse()

        with mock.patch(
            "peachjam_ml.views.get_message_snapshot",
            return_value=(SimpleNamespace(type="ai"), SimpleNamespace(metadata={})),
        ), mock.patch("peachjam_ml.views.langfuse", dummy_langfuse):
            response = self.client.post(
                f"/api/chats/{thread.pk}/messages/ai-1/vote-down"
            )

        self.assertEqual(response.status_code, 200)
        thread.refresh_from_db()
        self.assertEqual(thread.score, 1)
        self.assertEqual(dummy_langfuse.scores, [])
