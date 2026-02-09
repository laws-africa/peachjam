from django.test import TestCase

from peachjam.models import Judgment, LawReport, LawReportEntry, LawReportVolume


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
        self.assertEqual(
            "/law-reports/zambia-law-reports/", law_report.get_absolute_url()
        )

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
        self.assertEqual(
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

        LawReportEntry.objects.create(
            judgment=self.first_judgment,
            law_report_volume=self.volume_1,
        )
        LawReportEntry.objects.create(
            judgment=self.second_judgment,
            law_report_volume=self.volume_2,
        )

    def test_law_report_list_view(self):
        response = self.client.get("/law-reports/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.law_report.title)
        self.assertIn(self.law_report, response.context["law_reports"])

    def test_law_report_detail_view_shows_law_report_judgments_and_non_empty_volumes_only(
        self,
    ):
        response = self.client.get(self.law_report.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_judgment.title)
        self.assertContains(response, self.second_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertEqual(self.law_report, response.context["law_report"])
        self.assertIn(self.volume_1, response.context["law_report_volumes"])
        self.assertIn(self.volume_2, response.context["law_report_volumes"])
        self.assertNotIn(self.empty_volume, response.context["law_report_volumes"])
        self.assertTrue(response.context["hide_follow_button"])

    def test_law_report_volume_detail_view_filters_to_selected_volume(self):
        response = self.client.get(self.volume_1.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.second_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertEqual(self.volume_1, response.context["law_report_volume"])
