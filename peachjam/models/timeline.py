import logging
from collections import defaultdict
from itertools import islice

from django.conf import settings
from django.db import models
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from templated_email import send_templated_mail

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

    @classmethod
    def get_events(cls, user, before=None, limit=5):
        qs = cls.objects.filter(user_following__user=user).annotate(
            event_date=TruncDate("created_at")
        )

        # If "before" is provided, only consider earlier days
        if before:
            qs = qs.filter(event_date__lt=before)

        # get the next N distinct dates
        dates = qs.values("event_date").distinct().order_by("-event_date")[:limit]

        # Step 2: fetch all events for those dates
        qs = (
            cls.objects.filter(
                user_following__user=user,
                created_at__date__in=[d["event_date"] for d in dates],
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
        # step 3: group into {date: {followed_obj: [docs...]}}
        grouped = defaultdict(lambda: defaultdict(list))

        for ev in qs:
            for doc in ev.subject_documents.all():
                grouped[ev.event_date][ev.user_following].append(doc)

        # step 4: split docs into (first 10, rest)
        events = {}
        for date, objs in grouped.items():
            events[date] = []
            for obj, docs in objs.items():
                first_ten = list(islice(docs, 10))
                remaining = docs[10:]
                events[date].append((obj, (first_ten, remaining)))

        # Find the earliest date in this batch, so we know where to continue
        next_before = min(d["event_date"] for d in dates) if dates else None

        return events, next_before

    @classmethod
    def send_email_alerts(cls):
        from peachjam.tasks import (
            send_new_document_email_alert,
            send_saved_search_email_alert,
        )

        events = cls.objects.filter(email_alert_sent_at__isnull=True)
        if not events:
            log.info("No new events to alert.")
            return

        new_doc_users = (
            events.filter(event_type=cls.EventTypes.NEW_DOCUMENTS)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )
        for user_id in new_doc_users:
            send_new_document_email_alert(user_id)
        saved_search_users = (
            events.filter(event_type=cls.EventTypes.SAVED_SEARCH)
            .values_list("user_following__user_id", flat=True)
            .distinct()
        )
        for user_id in saved_search_users:
            send_saved_search_email_alert(user_id)

    @classmethod
    def send_saved_search_email_alert(cls, user):
        saved_searches = cls.objects.filter(
            email_alert_sent_at__isnull=True,
            event_type=cls.EventTypes.SAVED_SEARCH,
            user_following__user=user,
        ).select_related("user_following")

        if not saved_searches.exists():
            log.info(f"No saved search events to send for user {user.pk}")
            return
        log.info(f"Sending saved search email alerts for user {user.pk}")

        for ev in saved_searches:
            context = {
                "user": user,
                "hits": (ev.extra_data or {}).get("hits", []),
                "saved_search": ev.user_following.saved_search,
                "manage_url_path": reverse("search:saved_search_list"),
            }
            with override(user.userprofile.preferred_language.pk):
                send_templated_mail(
                    template_name="search_alert",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    context=context,
                )
                ev.email_alert_sent_at = timezone.now()
                ev.save(update_fields=["email_alert_sent_at"])

    @classmethod
    def send_new_document_email_alert(cls, user):
        new_document_events = (
            cls.objects.filter(
                email_alert_sent_at__isnull=True,
                event_type=cls.EventTypes.NEW_DOCUMENTS,
                user_following__user=user,
            )
            .select_related("user_following")
            .prefetch_related("subject_documents")
        )
        if not new_document_events.exists():
            log.info(f"No new document events to send for user {user.pk}")
            return
        log.info(f"Sending new document email alerts for user {user.pk}")

        follows_map = {}
        for ev in new_document_events:
            key = ev.user_following.followed_object
            follows_map.setdefault(key, set()).update(ev.subject_documents.all())
        follows = [
            {"followed_object": k, "documents": list(v)[:10]}
            for k, v in follows_map.items()
        ]

        context = {
            "followed_documents": follows,
            "user": user,
            "manage_url_path": reverse("user_following_list"),
        }
        with override(user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="user_following_alert",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                context=context,
            )

        # mark the events as sent after successful send. allows retries in case of failure.
        new_document_events.update(email_alert_sent_at=models.functions.Now())
