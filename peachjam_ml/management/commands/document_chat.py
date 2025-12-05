from collections.abc import Iterable
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from peachjam.models import CoreDocument
from peachjam_ml.chat.graphs import get_chat_config, get_chat_graph
from peachjam_ml.models import ChatThread


class Command(BaseCommand):
    help = "Stream the response from a new document chat for debugging purposes."

    def add_arguments(self, parser):
        parser.add_argument("user_id", type=int, help="Primary key of the user.")
        parser.add_argument(
            "document_id",
            type=int,
            help="Primary key of the CoreDocument to chat about.",
        )
        parser.add_argument(
            "-m",
            "--message",
            dest="message",
            help="Message to send. If omitted you will be prompted.",
        )

    def handle(self, *args, **options):
        user = self._get_user(options["user_id"])
        document = self._get_document(options["document_id"])
        message = self._normalise_message(options.get("message"))

        thread = ChatThread.objects.create(user=user, document=document)
        self.stdout.write(f"Created chat thread {thread.id}")

        try:
            with get_chat_graph() as graph:
                config = get_chat_config(thread)
                config["callbacks"] = []

                while True:
                    if not message:
                        message = self._prompt_for_message()
                        if not message:
                            break

                    self._run_chat_iteration(graph, config, user, document, message)
                    message = None
        finally:
            thread.delete()
            self.stdout.write(self.style.WARNING("Chat thread deleted."))

    def _run_chat_iteration(self, graph, config, user, document, message):
        snapshot = graph.get_state(config)
        state = snapshot.values or {
            "user_id": user.pk,
            "document_id": document.pk,
        }
        state["user_message"] = {
            "content": message,
            "id": str(uuid4()),
        }

        self.stdout.write("\nStreaming response:\n")
        for chunk in graph.stream(
            state,
            config,
            stream_mode=["updates", "messages"],
            durability="exit",
        ):
            # stream messages and then when that's done, just use the final (?) output message and return that
            # like we currently do
            # will need to be able to replace the streamed message with the full one in the final output
            # also will need to be able to know when to ignore tool calls, etc. (or show a different message)
            #   - eg need to know that reflecting "chatbot" is fine?
            #     - ignore tool calls
            print(chunk)
            continue
            streamed_message = self._extract_message(chunk)
            if streamed_message is None:
                continue
            if not self._is_ai_message(streamed_message):
                continue
            token = self._message_to_text(streamed_message)
            if token:
                self.stdout.write(token, ending="")
                self.stdout.flush()

        self.stdout.write("")  # newline after streaming finishes
        self.stdout.write(self.style.SUCCESS("Finished streaming response."))

    def _extract_message(self, chunk):
        if len(chunk) == 2:
            mode, payload = chunk
        else:
            _, mode, payload = chunk
        if mode != "messages":
            return None
        if isinstance(payload, tuple) and payload:
            return payload[0]
        return None

    def _message_to_text(self, message):
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, Iterable):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
            return text
        return str(content)

    def _is_ai_message(self, message):
        msg_type = getattr(message, "type", "")
        return isinstance(msg_type, str) and msg_type.lower().startswith("ai")

    def _prompt_for_message(self):
        self.stdout.write("")
        message = input("Enter message (or 'quit' to exit): ").strip()
        return self._normalise_message(message)

    def _normalise_message(self, message):
        if not message:
            return None
        stripped = message.strip()
        if not stripped or stripped.lower() in {"quit", "exit"}:
            return None
        return stripped

    def _get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise CommandError(f"User with id {user_id} does not exist.")

    def _get_document(self, document_id):
        try:
            return CoreDocument.objects.get(pk=document_id)
        except CoreDocument.DoesNotExist:
            raise CommandError(f"Document with id {document_id} does not exist.")
