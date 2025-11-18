import logging
from collections import defaultdict
from itertools import islice

from django.db import models
from django.db.models.functions import TruncDate
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

    @classmethod
    def add_new_documents_event(cls, follow, documents):
        event, _ = TimelineEvent.objects.get_or_create(
            user_following=follow,
            event_type=follow.get_event_type(),
            email_alert_sent_at__isnull=True,
        )
        event.append_documents(documents)
        return event

    @classmethod
    def add_new_search_hits_event(cls, follow, hits):
        # Prepare extra_data
        new_hits = []
        docs = []
        for hit in hits:
            doc = hit.document
            docs.append(doc)

            hit_dict = hit.as_dict()
            hit_dict["document"] = {
                "title": doc.title or "",
                "blurb": doc.blurb or "",
                "flynote": doc.flynote or "",
            }
            new_hits.append(hit_dict)

        event, created = TimelineEvent.objects.get_or_create(
            user_following=follow,
            event_type=follow.get_event_type(),
            email_alert_sent_at__isnull=True,
            defaults={"extra_data": {"hits": new_hits}},
        )

        if not created:
            existing = event.extra_data.get("hits", [])
            combined = {hit["id"]: hit for hit in existing}
            for hit in new_hits:
                combined[hit["id"]] = hit
            event.extra_data["hits"] = list(combined.values())
            event.save(update_fields=["extra_data"])

        event.append_documents(docs)
        return event

    @classmethod
    def get_user_timeline(cls, user, before=None, limit=5):
        qs = TimelineEvent.objects.filter(user_following__user=user).annotate(
            event_date=TruncDate("created_at")
        )

        if before:
            qs = qs.filter(event_date__lt=before)

        dates = qs.values("event_date").distinct().order_by("-event_date")[:limit]

        date_list = [d["event_date"] for d in dates]

        events_qs = (
            TimelineEvent.objects.filter(
                user_following__user=user,
                created_at__date__in=date_list,
            )
            .select_related("user_following")
            .prefetch_related(
                "subject_documents",
                "subject_documents__work",
                "subject_documents__labels",
            )
            .annotate(event_date=TruncDate("created_at"))
            .order_by("-event_date", "user_following__id", "-created_at")
        )

        grouped = defaultdict(lambda: defaultdict(list))

        for ev in events_qs:
            for doc in ev.subject_documents.all():
                grouped[ev.event_date][ev.user_following].append(doc)

        results = {}

        for date, by_follow in grouped.items():
            entries = []
            for follow, docs in by_follow.items():
                first = list(islice(docs, 10))
                rest = docs[10:]
                entries.append((follow, (first, rest)))
            results[date] = entries

        next_before = min(date_list) if date_list else None
        return results, next_before
