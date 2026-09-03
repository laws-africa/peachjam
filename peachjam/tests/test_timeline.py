from contextlib import contextmanager
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from countries_plus.models import Country
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import (
    Court,
    ExtractedCitation,
    Flynote,
    Journal,
    JournalArticle,
    Judgment,
    JudgmentFlynote,
    LawReport,
    LawReportEntry,
    LawReportVolume,
    Legislation,
    Locality,
    PeachJamSettings,
    Predicate,
    Relationship,
    SavedDocument,
    Taxonomy,
    TimelineEvent,
    UserFollowing,
    UserProfile,
    Work,
    pj_settings,
)
from peachjam.models.user_profile import default_email_alert_frequency
from peachjam.timeline_email_service import (
    EmailAlertBuilder,
    EmailAlertSummaryItem,
    TimelineEmailService,
)
from peachjam_search.models import SavedSearch
from peachjam_subs.models import Feature, Subscription


@contextmanager
def mock_email_alert_sender():
    with (
        override_settings(
            PEACHJAM={
                **settings.PEACHJAM,
                "EMAIL_ALERTS_ENABLED": True,
                "CUSTOMERIO_EMAIL_API_KEY": "test",
            },
            TEMPLATED_EMAIL_BACKEND="peachjam.emails.CustomerIOTemplateBackend",
        ),
        patch("peachjam.emails.APIClient.send_email") as mailer,
    ):
        yield mailer


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

    def test_locked_follow_does_not_create_timeline_events(self):
        self.follow.subscription_locked_at = datetime(2025, 7, 1)
        self.follow.subscription_lock_expires_at = datetime(2025, 9, 1)
        self.follow.save(
            update_fields=["subscription_locked_at", "subscription_lock_expires_at"]
        )
        Judgment.objects.create(
            case_name="Locked Follow Case",
            court=self.court,
            date=datetime(2025, 10, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )

        UserFollowing.update_follows_for_user(self.user)

        self.assertFalse(
            TimelineEvent.objects.filter(user_following__user=self.user).exists()
        )

    def test_send_email_alert_includes_followed_documents(self):
        topic = Taxonomy.add_root(name="Employment Law")
        topic_follow = UserFollowing.objects.create(user=self.user, taxonomy=topic)
        doc = Judgment.objects.first()
        TimelineEvent.add_new_documents_event(topic_follow, [doc])

        with mock_email_alert_sender() as mailer:
            TimelineEmailService.send_email_alert(self.user)

        self.assertEqual(1, mailer.call_count)
        request = mailer.call_args[0][0]
        self.assertEqual("Employment Law: 1 new judgment", str(request.subject))
        self.assertEqual("1 Employment Law judgment", request.preheader)
        self.assertIn("Here is your daily My Peachjam update.", request.body)
        self.assertIn("1 new judgment for", request.body)
        self.assertIn(
            f'href="https://example.com{topic.get_absolute_url()}">Employment Law</a>',
            request.body,
        )
        self.assertIn("From courts and topics you follow", request.body)
        self.assertIn("Manage alerts and delivery preferences", request.body)
        self.assertIn("View all updates in My Peachjam", request.body)
        self.assertIn('class="alert-document-list-item"', request.body)
        self.assertNotIn("Manage court and topic alerts", request.body)
        self.assertNotIn('href="#followed-documents"', request.body)

    def test_digest_frequency_uses_business_days(self):
        profile = self.user.userprofile

        profile.email_alert_frequency = profile.EmailAlertFrequency.DAILY
        self.assertTrue(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 14))
        )
        self.assertFalse(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 15))
        )

        profile.email_alert_frequency = profile.EmailAlertFrequency.WEEKLY
        self.assertTrue(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 17))
        )
        self.assertFalse(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 18))
        )

        profile.email_alert_frequency = profile.EmailAlertFrequency.MONTHLY
        self.assertTrue(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 3))
        )
        self.assertFalse(
            TimelineEmailService.is_email_alert_due(self.user, date(2026, 8, 4))
        )

    def test_my_lii_updates_email_alert_frequency(self):
        response = self.client.post(
            reverse("email_alerts"), {"email_alert_frequency": "weekly"}, follow=True
        )

        self.assertIn(
            "Your email update frequency has been updated to weekly.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )
        self.user.userprofile.refresh_from_db()
        self.assertEqual("weekly", self.user.userprofile.email_alert_frequency)

    def test_email_alerts_has_its_own_my_lii_tab(self):
        response = self.client.get(reverse("email_alerts"))

        self.assertContains(response, "Email updates")
        self.assertContains(response, 'class="nav-link active"', count=1)

    def test_follow_button_shows_following_status_and_email_updates_link(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_userfollowing")
        )

        response = self.client.get(
            reverse("user_following_button") + f"?court={self.court.pk}"
        )

        self.assertContains(response, "Following")
        self.assertContains(
            response,
            "You are following this court and will receive daily email updates.",
        )
        self.assertContains(response, reverse("email_alerts"))
        self.assertContains(response, "Unfollow")

    def test_follow_button_explains_when_email_updates_are_disabled(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_userfollowing")
        )
        self.user.userprofile.email_alert_frequency = (
            self.user.userprofile.EmailAlertFrequency.NONE
        )
        self.user.userprofile.save(update_fields=["email_alert_frequency"])

        response = self.client.get(
            reverse("user_following_button") + f"?court={self.court.pk}"
        )

        self.assertContains(
            response, "You are following this court, but email updates are disabled."
        )

    def test_follow_button_offers_follow_action_before_following(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_userfollowing")
        )
        self.follow.delete()

        response = self.client.get(
            reverse("user_following_button") + f"?court={self.court.pk}"
        )

        self.assertContains(response, "dropdown-toggle")
        self.assertContains(response, "Follow this court to receive updates")

    def test_anonymous_user_can_open_follow_account_modal_from_dropdown(self):
        self.client.logout()

        response = self.client.get(
            reverse("user_following_button") + f"?court={self.court.pk}"
        )

        self.assertContains(response, "dropdown-toggle")
        self.assertContains(response, "Follow this court to receive updates")
        self.assertContains(response, 'data-bs-target="#followModal"')

    def test_follow_actions_return_the_updated_button(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_userfollowing")
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="delete_userfollowing")
        )
        self.follow.delete()
        button_url = reverse("user_following_button") + f"?court={self.court.pk}"

        response = self.client.post(
            reverse("user_following_create") + f"?court={self.court.pk}"
        )
        self.assertRedirects(response, button_url, fetch_redirect_response=False)

        follow = UserFollowing.objects.get(user=self.user, court=self.court)
        response = self.client.post(
            reverse("user_following_delete", kwargs={"pk": follow.pk})
            + f"?court={self.court.pk}"
        )
        self.assertRedirects(response, button_url, fetch_redirect_response=False)

    def test_new_user_default_frequency_uses_site_settings(self):
        site_settings = pj_settings()
        site_settings.email_alert_default_frequency = "weekly"
        site_settings.save(update_fields=["email_alert_default_frequency"])

        self.assertEqual("weekly", default_email_alert_frequency())

    def test_site_frequency_choices_match_user_profile_choices(self):
        field = PeachJamSettings._meta.get_field("email_alert_default_frequency")
        self.assertEqual(UserProfile.EmailAlertFrequency.choices, field.choices)

    def test_digest_waits_24_hours_after_a_previous_delivery(self):
        topic = Taxonomy.add_root(name="Employment Law")
        follow = UserFollowing.objects.create(user=self.user, taxonomy=topic)
        document = Judgment.objects.first()
        previous_event = TimelineEvent.add_new_documents_event(follow, [document])
        previous_event.mark_as_sent()
        pending_event = TimelineEvent.add_new_documents_event(follow, [document])

        with (
            mock_email_alert_sender() as mailer,
            patch.object(TimelineEmailService, "is_email_alert_due", return_value=True),
        ):
            TimelineEmailService.send_email_alert(self.user)

        self.assertFalse(mailer.called)
        pending_event.refresh_from_db()
        self.assertIsNone(pending_event.email_alert_sent_at)

    def test_journal_follow_creates_new_documents_timeline_event(self):
        journal = Journal.objects.create(
            title="Regional Law Journal",
            slug="regional-law-journal",
        )
        follow = UserFollowing.objects.create(user=self.user, journal=journal)
        follow.last_alerted_at = self.last_alerted_at
        follow.save(update_fields=["last_alerted_at"])
        article = JournalArticle.objects.create(
            title="Fresh journal article",
            journal=journal,
            publisher="Publisher",
            date=datetime(2025, 10, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )

        UserFollowing.update_follows_for_user(self.user)

        event = TimelineEvent.objects.get(user_following=follow)
        self.assertEqual(TimelineEvent.EventTypes.NEW_DOCUMENTS, event.event_type)
        self.assertIn(article.work, event.subject_works.all())

    def test_law_report_follow_creates_new_documents_timeline_event(self):
        law_report = LawReport.objects.create(
            title="Regional Law Reports",
            slug="regional-law-reports",
        )
        volume = LawReportVolume.objects.create(
            title="Volume 1",
            slug="volume-1",
            law_report=law_report,
            year=2025,
        )
        follow = UserFollowing.objects.create(user=self.user, law_report=law_report)
        follow.last_alerted_at = self.last_alerted_at
        follow.save(update_fields=["last_alerted_at"])
        judgment = Judgment.objects.create(
            case_name="Reported case",
            court=self.court,
            date=datetime(2025, 10, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        LawReportEntry.objects.create(judgment=judgment, law_report_volume=volume)

        UserFollowing.update_follows_for_user(self.user)

        event = TimelineEvent.objects.get(user_following=follow)
        self.assertEqual(TimelineEvent.EventTypes.NEW_DOCUMENTS, event.event_type)
        self.assertIn(judgment.work, event.subject_works.all())

    def test_flynote_follow_creates_new_documents_timeline_event(self):
        root = Flynote.add_root(name="Administrative law")
        child = root.add_child(name="Decision-making")
        follow = UserFollowing.objects.create(user=self.user, flynote=root)
        follow.last_alerted_at = self.last_alerted_at
        follow.save(update_fields=["last_alerted_at"])
        judgment = Judgment.objects.create(
            case_name="Administrative decision case",
            court=self.court,
            date=datetime(2025, 10, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        JudgmentFlynote.objects.create(document=judgment, flynote=child)

        UserFollowing.update_follows_for_user(self.user)

        event = TimelineEvent.objects.get(user_following=follow)
        self.assertEqual(TimelineEvent.EventTypes.NEW_DOCUMENTS, event.event_type)
        self.assertIn(judgment.work, event.subject_works.all())

    def test_send_email_alert_includes_journal_follow(self):
        journal = Journal.objects.create(
            title="Regional Law Journal",
            slug="regional-law-journal",
        )
        follow = UserFollowing.objects.create(user=self.user, journal=journal)
        doc = Judgment.objects.first()
        TimelineEvent.add_new_documents_event(follow, [doc])

        with mock_email_alert_sender() as mailer:
            TimelineEmailService.send_email_alert(self.user)

        self.assertEqual(1, mailer.call_count)
        request = mailer.call_args[0][0]
        self.assertEqual("Regional Law Journal: 1 new judgment", str(request.subject))

    def test_send_email_alert_includes_flynote_follow(self):
        flynote = Flynote.add_root(name="Administrative law")
        follow = UserFollowing.objects.create(user=self.user, flynote=flynote)
        doc = Judgment.objects.first()
        TimelineEvent.add_new_documents_event(follow, [doc])

        with mock_email_alert_sender() as mailer:
            TimelineEmailService.send_email_alert(self.user)

        self.assertEqual(1, mailer.call_count)
        request = mailer.call_args[0][0]
        self.assertEqual("Administrative law: 1 new judgment", str(request.subject))

    def test_email_subject_shortens_long_entities_at_a_word_boundary(self):
        shortened = EmailAlertBuilder.shorten_subject_entity(
            "A subject entity with enough words to be shortened neatly while keeping the "
            "important legal context visible in the inbox " * 10
        )
        self.assertLessEqual(len(shortened), 500)
        self.assertTrue(shortened.endswith("…"))
        self.assertFalse(shortened[:-1].endswith(" "))

    def test_saved_search_email_copy_uses_advanced_query(self):
        saved_search = SavedSearch.objects.create(
            user=self.user,
            q=None,
            a='[{"fields": ["all"], "text": "constitutional rights"}]',
            filters="",
        )

        self.assertEqual(
            "constitutional rights in any field",
            EmailAlertBuilder.saved_search_text(saved_search),
        )
        self.assertEqual(
            "constitutional rights in any field: 2 new matches",
            EmailAlertBuilder.saved_search_subject(saved_search, 2),
        )
        self.assertEqual(
            "2 search results for “constitutional rights in any field”",
            EmailAlertBuilder.saved_search_label(
                "preheader", 2, saved_search=saved_search
            ),
        )

    def test_email_subject_prioritises_new_followed_documents(self):
        summary_items = [
            EmailAlertSummaryItem(
                label="",
                subject="New amendment to a saved Act",
                preheader="",
                priority=EmailAlertBuilder.summary_priority(
                    TimelineEvent.EventTypes.NEW_AMENDMENT
                ),
                section_id="relationships",
            ),
            EmailAlertSummaryItem(
                label="",
                subject="High Court of Tanzania: 2 new judgments",
                preheader="",
                priority=EmailAlertBuilder.summary_priority(
                    TimelineEvent.EventTypes.NEW_DOCUMENTS
                ),
                section_id="followed-documents",
            ),
            EmailAlertSummaryItem(
                label="",
                subject="New citation of a saved judgment",
                preheader="",
                priority=EmailAlertBuilder.summary_priority(
                    TimelineEvent.EventTypes.NEW_CITATION
                ),
                section_id="citations",
            ),
        ]

        self.assertEqual(
            "High Court of Tanzania: 2 new judgments and 2 more updates",
            EmailAlertBuilder.email_subject(summary_items),
        )

    def test_relationship_alert_copy_centralises_labels_and_priorities(self):
        event_type = TimelineEvent.EventTypes.NEW_AMENDMENT

        self.assertEqual(
            "2 new amendments",
            EmailAlertBuilder.relationship_label(event_type, "update", 2),
        )
        self.assertEqual(
            "New amendment to Saved Act",
            EmailAlertBuilder.relationship_label(
                event_type,
                "subject",
                1,
                document="Saved Act",
            ),
        )
        self.assertEqual(6, EmailAlertBuilder.summary_priority(event_type))

    def test_alert_label_copy_formats_each_presentation(self):
        documents = [SimpleNamespace(doc_type="judgment")]

        self.assertEqual(
            "2 new judgments for High Court of Tanzania",
            EmailAlertBuilder.followed_documents_label(
                "update",
                documents,
                2,
                followed_object="High Court of Tanzania",
            ),
        )
        self.assertEqual(
            "2 search results for “constitutional rights”",
            EmailAlertBuilder.saved_search_label(
                "preheader",
                2,
                saved_search=SimpleNamespace(q="constitutional rights"),
            ),
        )
        self.assertEqual(
            "2 new citations", EmailAlertBuilder.citation_label("update", 2)
        )


class TimelineRelationshipTests(TestCase):
    fixtures = [
        "tests/countries",
        "documents/sample_documents",
        "tests/users",
        "tests/products",
    ]

    def setUp(self):
        self.user = User.objects.first()

        amending_doc = Legislation.objects.create(
            jurisdiction=Country.objects.get(pk="AA"),
            locality=Locality.objects.get(code="au"),
            date=date.today(),
            title="amending test",
            frbr_uri_doctype="act",
            metadata_json={"commenced": True},
            language=Language.objects.first(),
        )
        repeal_doc = Legislation.objects.create(
            jurisdiction=Country.objects.get(pk="AA"),
            locality=Locality.objects.get(code="au"),
            title="repealing test",
            frbr_uri_doctype="act",
            date=date.today(),
            metadata_json={"commenced": True},
            language=Language.objects.first(),
        )

        overturning_doc = Judgment.objects.create(
            case_name="Overturning Case",
            court=Court.objects.get(code="ECOWASCJ"),
            date=date.today(),
            serial_number="52",
            frbr_uri_date="2026",
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="AA"),
            locality=Locality.objects.get(code="au"),
        )

        overturned_doc = Judgment.objects.create(
            case_name="Overturned Case",
            court=Court.objects.get(code="ECOWASCJ"),
            date=date.today(),
            serial_number="52",
            frbr_uri_date="2016",
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="AA"),
            locality=Locality.objects.get(code="au"),
        )

        self.followed_work = Work.objects.get(pk=2433)
        self.amending_work = amending_doc.work
        self.repealing_work = repeal_doc.work
        self.overturning_work = overturning_doc.work
        self.overturned_work = overturned_doc.work

        self.saved_followed = SavedDocument.objects.create(
            user=self.user, work=self.followed_work
        )
        self.follow_followed = UserFollowing.objects.get(
            user=self.user, saved_document=self.saved_followed
        )

        self.saved_overturned = SavedDocument.objects.create(
            user=self.user, work=self.overturned_work
        )
        self.follow_overturned = UserFollowing.objects.get(
            user=self.user, saved_document=self.saved_overturned
        )

        self.amended_predicate = Predicate.objects.create(
            name="amended by",
            slug="amended-by",
        )
        self.repealed_predicate, _ = Predicate.objects.get_or_create(
            name="repealed by",
            slug="repealed-by",
        )
        self.overturns_predicate, _ = Predicate.objects.get_or_create(
            name="overturns",
            slug="overturns",
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

    def test_locked_saved_document_does_not_create_relationship_event(self):
        self.saved_followed.subscription_locked_at = datetime(2025, 7, 1)
        self.saved_followed.subscription_lock_expires_at = datetime(2025, 9, 1)
        self.saved_followed.save(
            update_fields=["subscription_locked_at", "subscription_lock_expires_at"]
        )
        amendment = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=self.amending_work,
            predicate=self.amended_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)

        self.assertFalse(
            TimelineEvent.objects.filter(user_following=self.follow_followed).exists()
        )

    def test_update_new_relationship_skips_if_saved_document_has_no_document(self):
        undoc_work = Work.objects.create(
            title="Undocumented Work",
            frbr_uri="/akn/za/act/2024/undocumented",
        )
        saved_doc = SavedDocument.objects.create(user=self.user, work=undoc_work)
        follow = UserFollowing.objects.get(saved_document=saved_doc)

        amendment = Relationship.objects.create(
            subject_work=undoc_work,
            object_work=self.amending_work,
            predicate=self.amended_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)

        self.assertFalse(TimelineEvent.objects.filter(user_following=follow).exists())

    def test_update_new_relationship_skips_if_event_work_before_cutoff(self):
        old_doc = self.amending_work.documents.latest_expression().first()
        old_doc.date = self.follow_followed.cutoff_date - timedelta(days=1)
        old_doc.save(update_fields=["date"])

        amendment = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=self.amending_work,
            predicate=self.amended_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)

        self.assertFalse(
            TimelineEvent.objects.filter(
                user_following=self.follow_followed,
                event_type=TimelineEvent.EventTypes.NEW_AMENDMENT,
            ).exists()
        )

    def test_update_new_relationship_skips_if_event_work_has_no_document_expressions(
        self,
    ):
        undoc_event_work = Work.objects.create(
            title="Undocumented Event Work",
            frbr_uri="/akn/za/act/2024/no-event-docs",
        )

        amendment = Relationship.objects.create(
            subject_work=self.followed_work,
            object_work=undoc_event_work,
            predicate=self.amended_predicate,
        )

        UserFollowing.update_new_relationship_follows(amendment)

        self.assertFalse(
            TimelineEvent.objects.filter(
                user_following=self.follow_followed,
                event_type=TimelineEvent.EventTypes.NEW_AMENDMENT,
            ).exists()
        )

    def test_update_new_citation_skips_if_citing_work_has_no_documents(self):
        undoc_citing_work = Work.objects.create(
            title="Undocumented Citing Work",
            frbr_uri="/akn/za/act/2024/no-citing-docs",
        )

        citation = ExtractedCitation.objects.create(
            target_work=self.followed_work,
            citing_work=undoc_citing_work,
        )

        UserFollowing.update_new_citation_follows(citation)

        self.assertFalse(
            TimelineEvent.objects.filter(
                user_following=self.follow_followed,
                event_type=TimelineEvent.EventTypes.NEW_CITATION,
            ).exists()
        )

    def test_update_new_citation_skips_if_citing_work_before_cutoff(self):
        citing_doc = self.amending_work.documents.latest_expression().first()
        citing_doc.date = self.follow_followed.cutoff_date - timedelta(days=1)
        citing_doc.save(update_fields=["date"])

        citation = ExtractedCitation.objects.create(
            target_work=self.followed_work,
            citing_work=self.amending_work,
        )

        UserFollowing.update_new_citation_follows(citation)

        self.assertFalse(
            TimelineEvent.objects.filter(
                user_following=self.follow_followed,
                event_type=TimelineEvent.EventTypes.NEW_CITATION,
            ).exists()
        )

    def test_update_new_citation_creates_event_when_citing_work_after_cutoff(self):
        citing_doc = self.amending_work.documents.latest_expression().first()
        citing_doc.date = self.follow_followed.cutoff_date + timedelta(days=1)
        citing_doc.save(update_fields=["date"])

        citation = ExtractedCitation.objects.create(
            target_work=self.followed_work,
            citing_work=self.amending_work,
        )

        UserFollowing.update_new_citation_follows(citation)

        event = TimelineEvent.objects.get(
            user_following=self.follow_followed,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
        )
        self.assertIn(self.amending_work, event.subject_works.all())

    def test_locked_saved_document_does_not_create_citation_event(self):
        self.saved_followed.subscription_locked_at = datetime(2025, 7, 1)
        self.saved_followed.subscription_lock_expires_at = datetime(2025, 9, 1)
        self.saved_followed.save(
            update_fields=["subscription_locked_at", "subscription_lock_expires_at"]
        )
        citation = ExtractedCitation.objects.create(
            target_work=self.followed_work,
            citing_work=self.amending_work,
        )

        UserFollowing.update_new_citation_follows(citation)

        self.assertFalse(
            TimelineEvent.objects.filter(user_following=self.follow_followed).exists()
        )

    def test_send_email_alert_consolidates_relationship_updates(self):
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

        with mock_email_alert_sender() as mailer:
            TimelineEmailService.send_email_alert(self.user)

        self.assertEqual(1, mailer.call_count)
        transactional_message_ids = set()
        recipient_emails = set()
        subject_lines = set()

        for call in mailer.call_args_list:
            request = call.args[0]
            transactional_message_ids.add(request.transactional_message_id)
            recipient_emails.add(request.to)
            subject_lines.add(str(request.subject))
            self.assertEqual(
                {"id": self.user.userprofile.tracking_id_str},
                request.identifiers,
            )
            self.assertIn("<html", request.body)
            self.assertIn("utm_campaign=email_digest", request.body)
            self.assertIn("1 new amendment published for", request.body)
            self.assertIn("Manage alerts and delivery preferences", request.body)
            self.assertNotIn("Manage saved documents", request.body)
            self.assertEqual({}, request.attachments)

        self.assertEqual(
            {f"{settings.PEACHJAM['APP_NAME']}/generic"},
            transactional_message_ids,
        )
        self.assertEqual({self.user.email}, recipient_emails)
        self.assertEqual(1, len(subject_lines))
        self.assertTrue(subject_lines.pop().endswith("and 1 more update"))

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

    def test_send_new_citation_email_skips_follow_without_documents(self):
        undoc_work = Work.objects.create(
            title="Undocumented Work",
            frbr_uri="/akn/za/act/2024/no-docs",
        )
        saved_doc = SavedDocument.objects.create(user=self.user, work=undoc_work)
        follow = UserFollowing.objects.get(saved_document=saved_doc)

        TimelineEvent.add_new_citation_events(follow, self.amending_work)

        with mock_email_alert_sender() as mailer:
            TimelineEmailService.send_email_alert(self.user)

        self.assertFalse(mailer.called)
        event = TimelineEvent.objects.get(
            user_following=follow,
            event_type=TimelineEvent.EventTypes.NEW_CITATION,
        )
        self.assertIsNone(event.email_alert_sent_at)
