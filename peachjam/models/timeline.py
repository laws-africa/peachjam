from collections import defaultdict
from itertools import islice

from django.conf import settings
from django.db import models
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from templated_email import send_templated_mail


class TimelineEvent(models.Model):
    class EventTypes(models.TextChoices):
        NEW_DOCUMENTS = "new_documents", _("New Documents")

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
    created_at = models.DateTimeField(auto_now_add=True)
    user_notified = models.BooleanField(default=False)

    @classmethod
    def get_events(cls, user, before=None, limit=1):
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
                grouped[ev.event_date][ev.user_following.followed_object].append(doc)

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
        """
        Sends email alerts to the user following the documents if they haven't been notified yet.
        """
        for event in cls.objects.filter(user_notified=False):
            # Check if the user has any subject documents

            event.send_email_alert()

    def send_email_alert(self):

        context = {
            "followed_documents": self.subject_documents.all(),
            "user": self.user_following.user,
            "manage_url_path": reverse("user_following_list"),
        }
        with override(self.user_following.user.userprofile.preferred_language.pk):
            send_templated_mail(
                template_name="user_following_alert",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.user_following.user.email],
                context=context,
            )

        self.user_notified = True
        self.save(update_fields=["user_notified"])
