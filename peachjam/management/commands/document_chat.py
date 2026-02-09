import asyncio

from agents import Runner
from agents.stream_events import RawResponsesStreamEvent
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent

from peachjam.chat.agent import DocumentChat
from peachjam.models import ChatThread, CoreDocument


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
            while True:
                if not message:
                    message = self._prompt_for_message()
                    if not message:
                        break

                self._run_chat_iteration(thread, user, document, message)
                message = None
        finally:
            thread.delete()
            self.stdout.write(self.style.WARNING("Chat thread deleted."))

    def _run_chat_iteration(self, thread, user, document, message):
        self.stdout.write("\nStreaming response:\n")
        asyncio.run(
            self._stream_response(thread, user, document, message),
        )

        self.stdout.write("")  # newline after streaming finishes
        self.stdout.write(self.style.SUCCESS("Finished streaming response."))

    async def _stream_response(self, thread, user, document, message):
        chat = DocumentChat(thread)
        await chat.setup()

        result = Runner.run_streamed(
            chat.agent,
            input=message,
            context=chat.context,
            session=chat.session,
        )
        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent) and isinstance(
                event.data, ResponseTextDeltaEvent
            ):
                if event.data.delta:
                    print(event.data.delta, end="", flush=True)

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
