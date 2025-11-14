import logging

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

log = logging.getLogger(__name__)


class TimelineEvent(models.Model):
    class EventTypes(models.TextChoices):
        NEW_DOCUMENTS = "new_documents", _("New Documents")
        SAVED_SEARCH = "saved_search", _("Saved Search")

    user_following = models.ForeignKey(
        "peachjam.UserFollowing",
        on_delete=models.CASCADE,
        related_name="timeline_events",
    )
    subject_documents = models.ManyToManyField(
        "peachjam.CoreDocument", related_name="+"
    )
    event_type = models.CharField(
        max_length=256,
        choices=EventTypes.choices,
    )
    extra_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_alert_sent_at = models.DateTimeField(null=True)

    def mark_as_sent(self):
        self.email_alert_sent_at = timezone.now()
        self.save(update_fields=["email_alert_sent_at"])

    def append_documents(self, docs):
        """Tiny helper to avoid clutter."""
        self.subject_documents.add(*docs)

    def __str__(self):
        return f"{self.user_following} – {self.event_type}"
