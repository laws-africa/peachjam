from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.functions import TruncDate

from peachjam.models import CoreDocument, TimelineEvent

User = get_user_model()


class Command(BaseCommand):
    help = "Backfill timeline events for users"

    def handle(self, *args, **kwargs):
        users = User.objects.filter(following__isnull=False).distinct()
        total_users = users.count()
        ten_days_ago = datetime.now() - timedelta(days=10)
        self.stdout.write(f"Found {total_users} users with follows")

        for user in users:
            self.stdout.write(f"Processing user {user.username}...")
            with transaction.atomic():

                TimelineEvent.objects.filter(user_following__user=user).delete()
                for follow in user.following.all():
                    self.stdout.write(
                        f"Processing follow for {follow.followed_object}..."
                    )

                    # Get the documents followed by this user
                    docs = (
                        follow.get_documents_queryset()
                        .filter(created_at__date__gte=ten_days_ago)
                        .annotate(day=TruncDate("created_at"))
                        .order_by("day")
                    )
                    docs_by_day = {}
                    for doc in docs:
                        docs_by_day.setdefault(doc.day, []).append(doc)

                    for day, documents in docs_by_day.items():
                        # Check if an event already exists for this day
                        self.stdout.write(f"Checking for existing event on {day}...")

                        documents = CoreDocument.objects.filter(
                            pk__in=[doc.pk for doc in documents]
                        )
                        event = follow.create_timeline_event(documents)
                        if not event:
                            self.stdout.write(
                                f"No event created for {follow.followed_object} on {day}"
                            )
                            continue
                        event.created_at = day
                        event.email_alert_sent_at = day
                        event.save()
                self.stdout.write(f"Updated timeline for user {user.username}")
            self.stdout.write(
                self.style.SUCCESS("Successfully backfilled timelines for all users")
            )
