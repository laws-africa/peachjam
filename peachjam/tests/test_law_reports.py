import datetime

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import (
    Court,
    ExtractedCitation,
    Judgment,
    LawReport,
    LawReportEntry,
    LawReportVolume,
    Legislation,
)


class LawReportModelTestCase(TestCase):
    fixtures = [
        "tests/countries",
        "tests/languages",
        "tests/courts",
        "documents/sample_documents",
    ]

    def test_law_report_str_and_absolute_url(self):
        law_report = LawReport.objects.create(
            title="Zambia Law Reports", slug="zambia-law-reports"
        )

        self.assertEqual("Zambia Law Reports", str(law_report))
        self.assertIn("/law-reports/zambia-law-reports/", law_report.get_absolute_url())

    def test_law_report_volume_and_entry_str_and_absolute_url(self):
        law_report = LawReport.objects.create(
            title="Malawi Law Reports", slug="malawi-law-reports"
        )
        volume = LawReportVolume.objects.create(
            title="Volume 1",
            slug="volume-1",
            law_report=law_report,
            year=2018,
        )
        judgment = Judgment.objects.filter(published=True).first()
        entry = LawReportEntry.objects.create(
            judgment=judgment, law_report_volume=volume
        )

        self.assertEqual("Malawi Law Reports - Volume 1", str(volume))
        self.assertIn(
            "/law-reports/malawi-law-reports/volumes/volume-1/",
            volume.get_absolute_url(),
        )
        self.assertEqual(
            f"Malawi Law Reports - Volume 1 - {judgment}",
            str(entry),
        )


class LawReportViewsTestCase(TestCase):
    fixtures = [
        "tests/countries",
        "tests/languages",
        "tests/courts",
        "documents/sample_documents",
    ]

    def setUp(self):
        super().setUp()
        Judgment.objects.create(
            case_name="Not in Law report",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

        judgments = list(Judgment.objects.filter(published=True).order_by("date")[:3])

        self.law_report = LawReport.objects.create(
            title="East Africa Law Reports", slug="east-africa-law-reports"
        )
        self.volume_1 = LawReportVolume.objects.create(
            title="Volume 1",
            slug="volume-1",
            law_report=self.law_report,
            year=2018,
        )
        self.volume_2 = LawReportVolume.objects.create(
            title="Volume 2",
            slug="volume-2",
            law_report=self.law_report,
            year=2019,
        )
        self.empty_volume = LawReportVolume.objects.create(
            title="Volume 3",
            slug="volume-3",
            law_report=self.law_report,
            year=2020,
        )

        self.first_judgment = judgments[0]
        self.second_judgment = judgments[1]
        self.unrelated_judgment = judgments[2]
        legislations = list(
            Legislation.objects.filter(published=True).order_by("title")[:2]
        )
        self.cited_legislation = legislations[0]
        self.other_legislation = legislations[1]

        LawReportEntry.objects.create(
            judgment=self.first_judgment,
            law_report_volume=self.volume_1,
        )
        LawReportEntry.objects.create(
            judgment=self.second_judgment,
            law_report_volume=self.volume_2,
        )

        ExtractedCitation.objects.create(
            citing_work=self.first_judgment.work,
            target_work=self.second_judgment.work,
        )
        ExtractedCitation.objects.create(
            citing_work=self.first_judgment.work,
            target_work=self.cited_legislation.work,
        )
        ExtractedCitation.objects.create(
            citing_work=self.second_judgment.work,
            target_work=self.unrelated_judgment.work,
        )
        ExtractedCitation.objects.create(
            citing_work=self.second_judgment.work,
            target_work=self.other_legislation.work,
        )

    def test_law_report_list_view(self):
        response = self.client.get(reverse("law_report_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.law_report.title)
        self.assertIn(self.law_report, response.context["law_reports"])

    def test_law_report_detail_view_shows_law_report_judgments_and_non_empty_volumes_only(
        self,
    ):
        response = self.client.get(self.law_report.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        # The detail page now lists volumes, not judgments directly
        self.assertContains(response, self.volume_1.title)
        self.assertContains(response, self.volume_2.title)
        self.assertNotContains(response, self.empty_volume.title)
        self.assertEqual(self.law_report, response.context["law_report"])
        self.assertIn(self.volume_1, response.context["law_report_volumes"])
        self.assertIn(self.volume_2, response.context["law_report_volumes"])
        self.assertNotIn(self.empty_volume, response.context["law_report_volumes"])

    def test_law_report_volume_detail_view_filters_to_selected_volume(self):
        response = self.client.get(self.volume_1.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.second_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertEqual(self.volume_1, response.context["law_report_volume"])
        self.assertEqual("judgments", response.context["active_tab"])
        self.assertContains(response, "Sort by")
        self.assertNotContains(response, 'placeholder="Filter documents"')

    def test_law_report_volume_detail_view_cases_tab(self):
        url = reverse(
            "law_report_volume_cases_index",
            args=[self.law_report.slug, self.volume_1.slug],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual("cases", response.context["active_tab"])
        self.assertTrue(response.context.get("doc_table_toggle"))
        self.assertEqual("case", str(response.context["doc_count_noun"]))
        self.assertContains(response, self.second_judgment.title)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertContains(response, "Sort by")
        self.assertNotContains(response, 'placeholder="Filter documents"')

    def test_law_report_volume_detail_view_legislation_tab(self):
        url = reverse(
            "law_report_volume_legislation_index",
            args=[self.law_report.slug, self.volume_1.slug],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual("legislation", response.context["active_tab"])
        self.assertTrue(response.context.get("doc_table_toggle"))
        self.assertEqual("documents", str(response.context["doc_count_noun_plural"]))
        self.assertContains(response, self.cited_legislation.title)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.other_legislation.title)
        self.assertContains(response, "Sort by")
        self.assertNotContains(response, 'placeholder="Filter documents"')

    def test_law_report_volume_detail_view_invalid_tab_defaults_to_judgments(self):
        url = self.volume_1.get_absolute_url() + "?tab=invalid"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual("judgments", response.context["active_tab"])
