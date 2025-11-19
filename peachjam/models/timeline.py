import logging
from collections import defaultdict
from itertools import islice

from django.db import models
from django.db.models import Prefetch
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument

log = logging.getLogger(__name__)


class TimelineEventManager(models.Manager):
    def prefetch_subject_documents(self, user):
        """
        Returns a queryset with prefetched latest documents for each subject work.
        Does NOT attach them yet — call attach_subject_documents() after evaluation.
        """
        lang = user.userprofile.preferred_language.iso_639_3

        return (
            self.get_queryset()
            .select_related("user_following")
            .prefetch_related(
                Prefetch(
                    "subject_works__documents",
                    queryset=(
                        CoreDocument.objects.latest_expression()
                        .preferred_language(lang)
                        .prefetch_related("labels")
                    ),
                    to_attr="latest_docs",
                )
            )
        )

    def attach_subject_documents(self, event):
        """
        Attach subject_documents to a TimelineEvent instance.
        """
        docs = []
        for work in event.subject_works.all():
            if hasattr(work, "latest_docs"):
                docs.extend(work.latest_docs)

        event._cached_subject_documents = docs
        return event


class TimelineEvent(models.Model):
    class EventTypes(models.TextChoices):
        NEW_DOCUMENTS = "new_documents", _("New Documents")
        SAVED_SEARCH = "saved_search", _("Saved Search")

    objects = TimelineEventManager()

    user_following = models.ForeignKey(
        "peachjam.UserFollowing",
        on_delete=models.CASCADE,
        related_name="timeline_events",
    )
    subject_works = models.ManyToManyField("peachjam.Work", related_name="+")
    event_type = models.CharField(
        max_length=256,
        choices=EventTypes.choices,
    )
    extra_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_alert_sent_at = models.DateTimeField(null=True)

    @property
    def subject_documents(self):
        """
        Returns list of CoreDocuments.
        If prefetched via manager, returns cached.
        Otherwise runs a single efficient query.
        """
        if hasattr(self, "_cached_subject_documents"):
            return self._cached_subject_documents

        from peachjam.models import CoreDocument

        docs = list(
            CoreDocument.objects.latest_expression()
            .filter(work__in=self.subject_works.all())
            .prefetch_related("labels")
        )
        self._cached_subject_documents = docs
        return docs

    def mark_as_sent(self):
        self.email_alert_sent_at = timezone.now()
        self.save(update_fields=["email_alert_sent_at"])

    def append_documents(self, docs):
        """Tiny helper to avoid clutter."""
        works = {doc.work for doc in docs}
        self.subject_works.add(*works)

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
                "blurb": getattr(doc, "blurb", ""),
                "flynote": getattr(doc, "flynote", ""),
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
            TimelineEvent.objects.prefetch_subject_documents(user)
            .filter(
                user_following__user=user,
                created_at__date__in=date_list,
            )
            .annotate(event_date=TruncDate("created_at"))
            .order_by("-event_date", "user_following__id", "-created_at")
        )

        events_qs = [
            TimelineEvent.objects.attach_subject_documents(ev) for ev in events_qs
        ]

        grouped = defaultdict(lambda: defaultdict(list))

        for ev in events_qs:
            for doc in ev.subject_documents:
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
