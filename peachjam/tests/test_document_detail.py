from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.utils.translation import override
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

from peachjam.models import CitationLink, Judgment, Legislation
from peachjam.templatetags.peachjam import legislation_publication_detail
from peachjam.views.legislation import LegislationDetailView

User = get_user_model()


class LegislationFutureEventsTestCase(SimpleTestCase):
    def setUp(self):
        self.doc = Legislation(
            date=date(2026, 1, 23),
            metadata_json={"type_name": "legislation", "commenced": True},
            timeline_json=[],
        )
        self.view = LegislationDetailView()
        self.view.object = self.doc
        today = patch(
            "peachjam.views.legislation.timezone.localdate",
            return_value=date(2026, 11, 5),
        )
        today.start()
        self.addCleanup(today.stop)
        language = override("en")
        language.__enter__()
        self.addCleanup(language.__exit__, None, None, None)

    def test_future_commencement_notice_with_or_without_commenced_flag(self):
        for commenced in (True, False):
            with self.subTest(commenced=commenced):
                self.doc.metadata_json.update(
                    commenced=commenced,
                    commencements=[{"date": "2027-01-23"}],
                )
                notices = self.view.get_notices()
                html = render_to_string(
                    "peachjam/document/_warning_notices.html", {"messages": notices}
                )
                self.assertIn("alert-warning", html)
                self.assertIn(
                    "This legislation will come into force on 23 January 2027.", html
                )
                self.assertNotIn("has not yet come into force.", html)

    def test_notice_uses_main_date_when_commencement_list_is_absent_or_empty(self):
        for commencements in (None, [], [{"date": None}]):
            with self.subTest(commencements=commencements):
                self.doc.metadata_json.update(
                    commencement_date="2027-01-23", commencements=commencements
                )
                self.assertIn("23 January 2027", self.view.get_notices()[0]["html"])

    def test_past_and_today_commencements_have_no_future_notice(self):
        for commencement_date in ("2026-11-04", "2026-11-05"):
            with self.subTest(commencement_date=commencement_date):
                self.doc.metadata_json["commencements"] = [{"date": commencement_date}]
                self.assertEqual([], self.view.get_notices())

    def test_partial_commencement_notice_is_preserved(self):
        self.doc.metadata_json["commenced_in_full"] = False
        self.assertIn(
            "has not yet come into force in full", self.view.get_notices()[0]["html"]
        )

    def test_unknown_commencement_notice_is_preserved(self):
        self.doc.metadata_json["commenced"] = False
        self.assertEqual(
            "This legislation has not yet come into force.",
            self.view.get_notices()[0]["html"],
        )

    def render_history_entry(self, event, event_date):
        self.doc.timeline_json = [{"date": event_date, "events": [event]}]
        entry = self.view.get_timeline()[0]
        return render_to_string(
            "peachjam/document/_document_history_legislation_entry.html",
            {"entry": entry, "document": self.doc},
        )

    def test_future_commencement_wording_preserves_related_work_and_note(self):
        event = {
            "type": "commencement",
            "description": "Commenced by",
            "by_frbr_uri": "/akn/za/act/2026/1",
            "by_title": "Commencement notice",
            "note": "Only section 2",
        }
        html = self.render_history_entry(event, "2027-01-23")
        self.assertIn("Commences by", html)
        self.assertIn('href="/akn/za/act/2026/1"', html)
        self.assertIn("Commencement notice", html)
        self.assertIn("Only section 2", html)
        self.assertEqual("Commenced by", event["description"])

    def test_commencement_wording_changes_only_for_future_dates(self):
        for event_date, expected in (
            ("2026-11-04", "Commenced"),
            ("2026-11-05", "Commenced"),
            ("2026-11-06", "Commences"),
        ):
            with self.subTest(event_date=event_date):
                html = self.render_history_entry(
                    {"type": "commencement", "description": "Commenced"}, event_date
                )
                self.assertIn(expected, html)
                self.assertEqual(event_date > "2026-11-05", "Upcoming" in html)

    def test_all_future_event_types_are_marked_upcoming(self):
        for event_type, description in (
            ("publication", "Published in Government Gazette 53991"),
            ("assent", "Assented to"),
            ("amendment", "Revised by"),
            ("repeal", "Revoked by"),
            ("consolidation", "Consolidation"),
            ("chapter", "Chapter 12"),
        ):
            for event_date in ("2026-11-04", "2026-11-05", "2026-11-06"):
                with self.subTest(event_type=event_type, event_date=event_date):
                    html = self.render_history_entry(
                        {"type": event_type, "description": description}, event_date
                    )
                    self.assertIn(description, html)
                    self.assertEqual(event_date > "2026-11-05", "Upcoming" in html)


class LegislationPublicationTestCase(SimpleTestCase):
    def setUp(self):
        self.doc = Legislation(
            metadata_json={
                "publication_name": "Government Gazette",
                "publication_number": "1234",
                "publication_date": "1979-06-15",
            }
        )

    def test_publication_date_uses_active_language(self):
        with override("en"):
            self.assertEqual(
                legislation_publication_detail(self.doc),
                "Government Gazette 1234 on 15 June 1979",
            )
        with override("af"):
            self.assertEqual(
                legislation_publication_detail(self.doc),
                "Government Gazette 1234 on 15 Junie 1979",
            )

    def test_publication_detail_requires_name_and_number(self):
        metadata_variants = [
            {},
            {"publication_name": "Government Gazette"},
            {"publication_number": "1234"},
            {"publication_name": None, "publication_number": "1234"},
            {"publication_name": "Government Gazette", "publication_number": None},
        ]

        for metadata in metadata_variants:
            with self.subTest(metadata=metadata):
                self.doc.metadata_json = metadata
                self.assertIsNone(legislation_publication_detail(self.doc))

    def test_publication_detail_handles_missing_null_or_invalid_date(self):
        date_variants = [
            {},
            {"publication_date": None},
            {"publication_date": ""},
            {"publication_date": "not-a-date"},
            {"publication_date": "1979-99-15"},
        ]

        for date_metadata in date_variants:
            with self.subTest(date_metadata=date_metadata):
                self.doc.metadata_json = {
                    "publication_name": "Government Gazette",
                    "publication_number": "1234",
                    **date_metadata,
                }

                self.assertEqual(
                    legislation_publication_detail(self.doc),
                    "Government Gazette 1234",
                )

    def test_publication_page_handles_missing_fields(self):
        metadata_variants = [
            {},
            {"publication_document": None},
            {"publication_document": {}},
            {"publication_document": {"start_page": None}},
        ]

        for metadata in metadata_variants:
            with self.subTest(metadata=metadata):
                self.doc.metadata_json = metadata
                self.assertIsNone(self.doc.publication_page)

    def test_publication_page(self):
        self.doc.metadata_json["publication_document"] = {"start_page": 12}

        self.assertEqual(self.doc.publication_page, 12)


class DocumentViewTestCase(WebTest):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def test_document_citation_links(self):
        doc = Judgment.objects.first()
        response = self.app.get(doc.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<script id="citation-links" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="provision-relationships" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="provision-enrichments-json" type="application/json">[]</script>',
            html=True,
        )
        self.assertContains(
            response,
            '<script id="incoming-citations-json" type="application/json">[]</script>',
            html=True,
        )

    def test_external_document_citation_links_include_external_flag(self):
        doc = Judgment.objects.first()
        CitationLink.objects.create(
            document=doc,
            text="External citation",
            url="https://example.com/doc",
            target_id="page-1",
            target_selectors=[],
        )

        response = self.app.get(doc.get_absolute_url())

        self.assertContains(response, '"is_external": true')

    def test_legislation_images_remain_prefixed_after_loading_deferred_timeline(self):
        doc = Legislation.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2020-10-22"
        )
        self.assertIn("timeline_json", doc.get_deferred_fields())
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = '<div><img src="media/image.png"></div>'
        doc_content.save()

        response = self.app.get(doc.get_absolute_url())

        self.assertContains(
            response,
            f'src="{doc.expression_frbr_uri}/media/image.png"',
        )
        self.assertContains(response, 'loading="lazy"')
        self.assertNotContains(response, 'src="media/image.png"')


class RestrictedDocumentsTestCase(WebTest):
    fixtures = [
        "tests/users",
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.judgment = Judgment.objects.order_by("pk").first()
        self.assertIsNotNone(
            self.judgment, "Expected at least one judgment in fixtures"
        )
        self.judgment.restricted = True
        self.judgment.save()

        group = Group.objects.get(name="Officers")
        assign_perm("view_judgment", group, self.judgment)

    def test_restricted_document_unauthorized(self):
        unauthorized_user = User.objects.get(username="user@example.com")
        response = self.app.get(
            self.judgment.get_absolute_url(), user=unauthorized_user, expect_errors=True
        )
        self.assertIn("Permission denied", response.text)
        self.assertEqual(response.status_code, 403)

    def test_restricted_document_authorized(self):
        authorized_user = User.objects.get(username="officer@example.com")
        response = self.app.get(self.judgment.get_absolute_url(), user=authorized_user)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("public", response.headers.get("Cache-Control", ""))


class HistoricalLegislationCacheHeadersTestCase(TestCase):
    fixtures = [
        "tests/users",
        "tests/countries",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.doc = Legislation.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2010-08-09"
        )

    def test_anonymous_historical_legislation_has_no_cache(self):
        response = self.client.get(self.doc.get_absolute_url())
        # ensure the document content is NOT there
        self.assertNotIn('class="document-content"', response.content.decode())
        self.assertIn("no-cache", response.headers.get("Cache-Control", ""))

    def test_logged_in_historical_legislation_has_no_cache(self):
        user = User.objects.get(username="user@example.com")
        perm = Permission.objects.get(codename="can_view_historical_legislation")
        user.user_permissions.add(perm)
        self.client.force_login(user)
        response = self.client.get(self.doc.get_absolute_url())
        # ensure the document content is there and not a "permission denied" error
        self.assertIn('class="document-content"', response.content.decode())
        self.assertIn("no-cache", response.headers.get("Cache-Control", ""))

    def test_most_recent_legislation_is_cacheable(self):
        doc = Legislation.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2020-10-22"
        )
        response = self.client.get(doc.get_absolute_url())
        # ensure the document content is there and not a "permission denied" error
        self.assertIn('class="document-content"', response.content.decode())
        cache_control = response.headers.get("Cache-Control", "")
        self.assertIn("public", cache_control)
        self.assertNotIn("no-cache", cache_control)


class LegislationAmendmentNoticeTestCase(TestCase):
    fixtures = [
        "tests/countries",
        "tests/languages",
        "documents/sample_documents",
    ]

    def setUp(self):
        self.doc = Legislation.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2020-10-22"
        )
        self.doc.date = date(2026, 1, 30)
        self.doc.metadata_json = {
            "commenced": True,
            "type_name": "legislation",
            "points_in_time": [
                {
                    "date": "2026-01-30",
                    "expressions": [
                        {"expression_frbr_uri": "/akn/za/act/1979/70/eng@2026-01-30"}
                    ],
                }
            ],
            "work_amendments": [
                {
                    "date": "2026-08-01",
                    "title": "Future amendment",
                }
            ],
        }
        self.doc.timeline_json = [
            {
                "date": "2026-08-01",
                "events": [
                    {
                        "type": "amendment",
                        "description": "Amended by",
                    }
                ],
            }
        ]

    def get_view(self):
        view = LegislationDetailView()
        view.object = self.doc
        return view

    @patch("peachjam.views.legislation.timezone.localdate")
    def test_future_amendments_do_not_trigger_outstanding_notice(self, localdate):
        localdate.return_value = date(2026, 6, 28)

        notices = self.get_view().get_notices()
        timeline = self.get_view().get_timeline()

        self.assertFalse(
            any("outstanding amendments" in notice["html"] for notice in notices)
        )
        self.assertFalse(timeline[0].get("contains_unapplied_amendment", False))

    @patch("peachjam.views.legislation.timezone.localdate")
    def test_effective_unapplied_amendments_trigger_outstanding_notice(self, localdate):
        localdate.return_value = date(2026, 8, 2)

        notices = self.get_view().get_notices()
        timeline = self.get_view().get_timeline()

        self.assertTrue(
            any("outstanding amendments" in notice["html"] for notice in notices)
        )
        self.assertTrue(timeline[0]["contains_unapplied_amendment"])
