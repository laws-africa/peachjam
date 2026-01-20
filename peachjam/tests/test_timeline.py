from datetime import datetime
from unittest.mock import patch

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.test import TestCase, override_settings
from languages_plus.models import Language

from peachjam.models import (
    Court,
    Judgment,
    Predicate,
    Relationship,
    SavedDocument,
    TimelineEvent,
    UserFollowing,
    Work,
)
from peachjam.timeline_email_service import TimelineEmailService
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


class TimelineRelationshipTests(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
        "tests/products",
    ]

    def setUp(self):
        self.user = User.objects.first()

        self.followed_work = Work.objects.get(pk=2433)
        self.amending_work = Work.objects.get(pk=3704)
        self.repealing_work = Work.objects.get(pk=3716)

        self.overturning_work = Work.objects.get(pk=1132)
        self.overturned_work = Work.objects.get(pk=1031)

        self.saved_followed = SavedDocument.objects.create(
            user=self.user, work=self.followed_work
        )
        self.follow_followed = UserFollowing.objects.create(
            user=self.user, saved_document=self.saved_followed
        )

        self.saved_overturned = SavedDocument.objects.create(
            user=self.user, work=self.overturned_work
        )
        self.follow_overturned = UserFollowing.objects.create(
            user=self.user, saved_document=self.saved_overturned
        )

        self.amended_predicate = Predicate.objects.create(
            name="amended by",
            slug="amended-by",
            verb="is amended by",
            reverse_verb="amends",
        )
        self.repealed_predicate = Predicate.objects.create(
            name="repealed by",
            slug="repealed-by",
            verb="is repealed by",
            reverse_verb="repeals",
        )
        self.overturns_predicate = Predicate.objects.create(
            name="overturns",
            slug="overturns",
            verb="overturns",
            reverse_verb="is overturned by",
        )

    def test_update_new_relationship_follows_creates_timeline_events(self):
        amendment = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=self.amending_work,
            predicate=self.amended_predicate,
        )
        repeal = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=self.repealing_work,
            predicate=self.repealed_predicate,
        )
        overturn = Relationship.objects.create(
            subject_work=self.overturning_work,
            object_work=self.overturned_work,
            predicate=self.overturns_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)
        UserFollowing.update_new_relationship_follows(repeal)
        UserFollowing.update_new_relationship_follows(overturn)

        amendment_event = TimelineEvent.objects.get(
            user_following=self.follow_followed,
            event_type=TimelineEvent.EventTypes.NEW_AMENDMENT,
        )
        self.assertIn(self.amending_work, amendment_event.subject_works.all())

        repeal_event = TimelineEvent.objects.get(
            user_following=self.follow_followed,
            event_type=TimelineEvent.EventTypes.NEW_REPEAL,
        )
        self.assertIn(self.repealing_work, repeal_event.subject_works.all())

        overturn_event = TimelineEvent.objects.get(
            user_following=self.follow_overturned,
            event_type=TimelineEvent.EventTypes.NEW_OVERTURN,
        )
        self.assertIn(self.overturning_work, overturn_event.subject_works.all())

    def test_send_new_relationship_email_sends_separate_templates(self):
        amendment = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=self.amending_work,
            predicate=self.amended_predicate,
        )
        overturn = Relationship.objects.create(
            subject_work=self.overturning_work,
            object_work=self.overturned_work,
            predicate=self.overturns_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)
        UserFollowing.update_new_relationship_follows(overturn)

        with (
            override_settings(
                PEACHJAM={**settings.PEACHJAM, "EMAIL_ALERTS_ENABLED": True}
            ),
            patch("peachjam.timeline_email_service.send_templated_mail") as mailer,
        ):
            TimelineEmailService.send_new_relationship_email(self.user)

        template_names = {
            call.kwargs["template_name"] for call in mailer.call_args_list
        }
        self.assertEqual(
            {"new_relationship_alert", "new_overturn_alert"}, template_names
        )

        sent_events = TimelineEvent.objects.filter(
            user_following__user=self.user,
            event_type__in=[
                TimelineEvent.EventTypes.NEW_AMENDMENT,
                TimelineEvent.EventTypes.NEW_OVERTURN,
            ],
        )
        self.assertTrue(sent_events.exists())
        self.assertTrue(
            all(event.email_alert_sent_at for event in sent_events),
        )
