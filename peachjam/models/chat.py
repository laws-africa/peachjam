import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ChatThread(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_threads"
    )
    document = models.ForeignKey("peachjam.CoreDocument", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    score = models.IntegerField(default=0)
    messages_json = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]

    async def asave_message_history(self, messages):
        self.messages_json = messages
        await self.asave()

    def get_thread_messages(self) -> list[dict]:
        return self.messages_json or []

    def get_message_by_id(self, message_id: str) -> dict | None:
        for message in self.get_thread_messages():
            if message.get("id") == message_id:
                return message
        return None

    @classmethod
    def count_active_for_user(cls, user):
        """How many active chat threads does the user have? Used to enforce monthly limits."""
        now = timezone.now()
        month_start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return (
            cls.objects.filter(
                user=user,
                updated_at__gte=month_start,
            )
            .values("document_id")
            .distinct()
            .count()
        )
