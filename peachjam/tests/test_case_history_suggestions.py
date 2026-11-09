from datetime import date

from countries_plus.models import Country
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django_webtest import WebTest
from languages_plus.models import Language

from peachjam.analysis.case_history import CaseHistorySuggestionService
from peachjam.models import (
    CaseHistory,
    CaseHistorySuggestion,
    Court,
    CourtClass,
    Judgment,
)


class CaseHistorySuggestionTestMixin:
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    @classmethod
    def setUpTestData(cls):
        cls.country = Country.objects.get(pk="ZM")
        cls.language = Language.objects.get(pk="en")
        apex = CourtClass.objects.create(name="Apex Courts", slug="apex-courts")
        high = CourtClass.objects.create(name="High Courts", slug="high-courts")
        cls.sca = Court.objects.create(
            name="Supreme Court of Appeal", code="ZASCA", court_class=apex
        )
        cls.high_court = Court.objects.create(
            name="High Court", code="ZAGPJHC", court_class=high
        )

    def make_judgment(self, case_name, judgment_date, court):
        return Judgment.objects.create(
            case_name=case_name,
            court=court,
            date=judgment_date,
            language=self.language,
            jurisdiction=self.country,
        )

    def make_suggestion(self):
        historical = self.make_judgment(
            "Alpha Limited v Beta Holdings", date(2020, 3, 10), self.high_court
        )
        judgment = self.make_judgment(
            "Beta Holdings v Alpha Limited", date(2021, 4, 20), self.sca
        )
        return CaseHistorySuggestion.objects.create(
            judgment=judgment,
            historical_judgment=historical,
            relationship_type=CaseHistorySuggestion.RelationshipType.APPEAL_FROM,
            confidence=CaseHistorySuggestion.Confidence.HIGH,
            disposition=CaseHistorySuggestion.Disposition.AUTO_ACCEPT,
            score=27,
            matching_methods=["neutral_citation", "citation_link"],
            evidence="On appeal from the judgment of the High Court.",
        )


class TestCaseHistorySuggestion(CaseHistorySuggestionTestMixin, TestCase):
    def test_accept_creates_authoritative_case_history(self):
        suggestion = self.make_suggestion()
        reviewer = User.objects.get(username="admin@example.com")

        case_history = suggestion.accept(reviewer)

        self.assertEqual(CaseHistorySuggestion.Status.ACCEPTED, suggestion.status)
        self.assertEqual(reviewer, suggestion.reviewed_by)
        self.assertEqual(case_history, suggestion.case_history)
        self.assertEqual(suggestion.judgment.work, case_history.judgment_work)
        self.assertEqual(
            suggestion.historical_judgment.work,
            case_history.historical_judgment_work,
        )
        self.assertEqual(suggestion.historical_judgment.court, case_history.court)
        self.assertEqual(suggestion.historical_judgment.date, case_history.date)

        self.assertEqual(case_history, suggestion.accept(reviewer))
        self.assertEqual(1, CaseHistory.objects.count())

    def test_reject_retains_suggestion(self):
        suggestion = self.make_suggestion()
        reviewer = User.objects.get(username="admin@example.com")
        suggestion.editor_note = "This is a cited authority, not an earlier stage."

        suggestion.reject(reviewer)

        suggestion.refresh_from_db()
        self.assertEqual(CaseHistorySuggestion.Status.REJECTED, suggestion.status)
        self.assertEqual(reviewer, suggestion.reviewed_by)
        self.assertIsNotNone(suggestion.reviewed_at)
        self.assertFalse(CaseHistory.objects.exists())

    def test_service_creates_deterministic_suggestion(self):
        historical = self.make_judgment(
            "Alpha Limited v Beta Holdings", date(2020, 3, 10), self.high_court
        )
        judgment = self.make_judgment(
            "Beta Holdings v Alpha Limited", date(2021, 4, 20), self.sca
        )
        content = judgment.get_or_create_document_content()
        content.content_text = (
            "This is an appeal against the judgment of the High Court in "
            f"Alpha Limited v Beta Holdings {historical.mnc}."
        )
        content.save()

        count = CaseHistorySuggestionService().suggest(judgment)

        self.assertEqual(1, count)
        suggestion = CaseHistorySuggestion.objects.get()
        self.assertEqual(judgment, suggestion.judgment)
        self.assertEqual(historical, suggestion.historical_judgment)
        self.assertEqual(
            CaseHistorySuggestion.RelationshipType.APPEAL_FROM,
            suggestion.relationship_type,
        )
        self.assertIn("neutral_citation", suggestion.matching_methods)
        self.assertEqual(
            CaseHistorySuggestion.Disposition.AUTO_ACCEPT,
            suggestion.disposition,
        )

    def test_service_rechecks_later_judgments_when_history_is_added(self):
        historical = self.make_judgment(
            "Alpha Limited v Beta Holdings", date(2020, 3, 10), self.high_court
        )
        historical_content = historical.get_or_create_document_content()
        historical_content.content_text = "Judgment in the dispute."
        historical_content.save()
        later = self.make_judgment(
            "Beta Holdings v Alpha Limited", date(2021, 4, 20), self.sca
        )
        later_content = later.get_or_create_document_content()
        later_content.content_text = (
            "This is an appeal against the judgment of the High Court in "
            f"Alpha Limited v Beta Holdings {historical.mnc}."
        )
        later_content.save()

        count = CaseHistorySuggestionService().suggest(historical)

        self.assertEqual(1, count)
        suggestion = CaseHistorySuggestion.objects.get()
        self.assertEqual(later, suggestion.judgment)
        self.assertEqual(historical, suggestion.historical_judgment)


class TestCaseHistorySuggestionAdmin(CaseHistorySuggestionTestMixin, WebTest):
    def setUp(self):
        self.app.set_user(User.objects.get(username="admin@example.com"))

    def test_judgment_editor_has_case_history_suggestion_tab(self):
        suggestion = self.make_suggestion()
        url = reverse(
            "admin:peachjam_judgment_change",
            kwargs={"object_id": suggestion.judgment_id},
        )

        response = self.app.get(url)

        self.assertContains(response, "Case history suggestions")
        self.assertContains(response, str(suggestion.historical_judgment))
        self.assertContains(response, "On appeal from the judgment")
        self.assertContains(response, "Strong suggestion")

    def test_editor_can_accept_suggestion(self):
        suggestion = self.make_suggestion()
        url = reverse(
            "admin:peachjam_judgment_change",
            kwargs={"object_id": suggestion.judgment_id},
        )
        form = self.app.get(url).forms["judgment_form"]
        form["peachjam-casehistorysuggestion-0-status"] = (
            CaseHistorySuggestion.Status.ACCEPTED
        )

        response = form.submit(name="_continue")

        self.assertRedirects(response, url)
        suggestion.refresh_from_db()
        self.assertEqual(CaseHistorySuggestion.Status.ACCEPTED, suggestion.status)
        self.assertEqual(
            User.objects.get(username="admin@example.com"), suggestion.reviewed_by
        )
        self.assertIsNotNone(suggestion.case_history)
