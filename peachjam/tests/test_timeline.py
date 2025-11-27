from datetime import datetime

from countries_plus.models import Country
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import Court, Judgment, TimelineEvent, UserFollowing
from peachjam_subs.models import Feature, Subscription


class TimelineViewTest(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
        "tests/products",
    ]

    def setUp(self):
        feature = Feature.objects.get(pk=1)

        # attach permissions by codename/app_label
        perms = Permission.objects.filter(
            content_type__app_label="peachjam",
            codename__in=[
                "add_userfollowing",
                "delete_userfollowing",
                "view_userfollowing",
            ],
        )
        feature.permissions.set(perms)

        self.user = User.objects.first()
        Subscription.get_or_create_active_for_user(self.user)
        self.client._login(self.user, "django.contrib.auth.backends.ModelBackend")

        self.court = Court.objects.get(code="ECOWASCJ")
        self.follow = UserFollowing.objects.create(user=self.user, court=self.court)
        self.last_alerted_at = datetime(2025, 7, 1)
        self.follow.last_alerted_at = self.last_alerted_at
        self.initial_documents_count = Judgment.objects.filter(
            court=self.court, created_at__gte=self.last_alerted_at
        ).count()
        self.follow.save()

    def test_timeline_create_and_update(self):
        # Initially, no timeline events
        self.assertEqual(0, TimelineEvent.objects.count())
        date = datetime(2025, 10, 1)
        Judgment.objects.create(
            case_name="New Case",
            court=self.court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        Judgment.objects.create(
            case_name="New Case 2",
            court=self.court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        date = datetime(2000, 10, 1)
        # An old judgment that should not be included
        Judgment.objects.create(
            case_name="Old Case",
            court=self.court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )

        # Update the timeline for the user → should create one event
        UserFollowing.update_follows_for_user(self.user)
        self.assertEqual(
            1, TimelineEvent.objects.filter(user_following__user=self.user).count()
        )
        subject_docs = TimelineEvent.objects.filter(
            user_following__user=self.user
        ).values_list("subject_works__documents__id", flat=True)
        self.assertEqual(2, subject_docs.count())

        # Create a new judgment and update timeline
        # → should NOT create a new event, but subject doc count should increase
        date = datetime(2025, 10, 1)
        j = Judgment.objects.create(
            case_name="New Case 3",
            court=self.court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        UserFollowing.update_follows_for_user(self.user)
        self.assertEqual(1, TimelineEvent.objects.count())
        subject_docs = TimelineEvent.objects.filter(
            user_following__user=self.user
        ).values_list("subject_works__documents__id", flat=True)
        self.assertEqual(3, subject_docs.count())
        self.assertIn(j.pk, subject_docs)

        # Send timeline emails, then create another doc and update timeline
        # → should create a NEW timeline event, subject doc count should increase
        TimelineEvent.objects.all().update(email_alert_sent_at=date)
        j = Judgment.objects.create(
            case_name="Another Case",
            court=self.court,
            date=date,
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        UserFollowing.update_follows_for_user(self.user)
        self.assertEqual(2, TimelineEvent.objects.count())
        subject_docs = TimelineEvent.objects.filter(
            user_following__user=self.user
        ).values_list("subject_works__documents__id", flat=True)
        self.assertEqual(4, subject_docs.count())
        self.assertIn(j.pk, subject_docs)
