from collections import defaultdict
from itertools import islice

from django.db.models.functions import TruncDate

from peachjam.models import TimelineEvent


class TimelineQueryService:
    @staticmethod
    def get_user_timeline(user, before=None, limit=5):
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
