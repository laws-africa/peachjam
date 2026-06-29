from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django_webtest import WebTest
from guardian.shortcuts import assign_perm

from peachjam.models import CitationLink, Judgment, Legislation
from peachjam.views.legislation import LegislationDetailView

User = get_user_model()


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
