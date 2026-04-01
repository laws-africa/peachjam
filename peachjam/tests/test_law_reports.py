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
        self.original_cited_legislation_date = self.cited_legislation.date
        duplicated_legislation_fields = {
            field.attname: getattr(self.cited_legislation, field.attname)
            for field in Legislation._meta.concrete_fields
            if not field.primary_key
            and field.attname
            not in {
                "polymorphic_ctype_id",
                "created_by_id",
                "created_at",
                "updated_at",
                "work_frbr_uri",
                "expression_frbr_uri",
            }
        }
        duplicated_legislation_fields["work_id"] = self.cited_legislation.work_id
        duplicated_legislation_fields["date"] = (
            self.cited_legislation.date + datetime.timedelta(days=365)
        )
        self.latest_cited_legislation = Legislation.objects.create(
            **duplicated_legislation_fields
        )
        Legislation.objects.filter(pk=self.latest_cited_legislation.pk).update(
            work_id=self.cited_legislation.work_id,
            work_frbr_uri=self.cited_legislation.work_frbr_uri,
        )
        self.latest_cited_legislation.refresh_from_db()

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
        self.assertTemplateUsed(response, "peachjam/law_report/law_report_detail.html")
        self.assertContains(response, "Volumes")
        self.assertContains(response, self.volume_1.title)
        self.assertContains(response, self.volume_2.title)
        self.assertNotContains(response, self.empty_volume.title)
        self.assertNotContains(response, self.first_judgment.title)
        self.assertNotContains(response, 'placeholder="Filter documents"', html=False)
        self.assertContains(
            response,
            reverse("user_following_button") + f"?law_report={self.law_report.pk}",
        )
        self.assertEqual(self.law_report, response.context["law_report"])
        self.assertIn(self.volume_1, response.context["law_report_volumes"])
        self.assertIn(self.volume_2, response.context["law_report_volumes"])
        self.assertNotIn(self.empty_volume, response.context["law_report_volumes"])
        self.assertEqual(
            [self.volume_2, self.volume_1], list(response.context["law_report_volumes"])
        )

    def test_law_report_volume_detail_view_filters_to_selected_volume(self):
        response = self.client.get(self.volume_1.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "peachjam/law_report/law_report_volume_detail.html"
        )
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.second_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertNotContains(response, "Back to law report")
        self.assertContains(
            response,
            reverse("user_following_button") + f"?law_report={self.law_report.pk}",
        )
        self.assertContains(
            response, '<h1 class="mb-0">East Africa Law Reports</h1>', html=False
        )
        self.assertContains(response, '<h2 class="h4 mb-0">Volume 1</h2>', html=False)
        self.assertContains(response, "nav nav-tabs border-bottom", html=False)
        self.assertEqual(self.volume_1, response.context["law_report_volume"])
        self.assertEqual("judgments", response.context["active_tab"])
        self.assertContains(response, 'placeholder="Filter documents"', html=False)

    def test_law_report_volume_detail_view_cases_tab(self):
        url = reverse(
            "law_report_volume_cases_index",
            args=[self.law_report.slug, self.volume_1.slug],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "peachjam/law_report/law_report_volume_cases_index.html"
        )
        self.assertEqual("cases", response.context["active_tab"])
        self.assertTrue(response.context.get("doc_table_toggle"))
        self.assertContains(
            response,
            reverse("user_following_button") + f"?law_report={self.law_report.pk}",
        )
        self.assertContains(
            response, '<h1 class="mb-0">East Africa Law Reports</h1>', html=False
        )
        self.assertContains(response, '<h2 class="h4 mb-0">Volume 1</h2>', html=False)
        self.assertNotContains(response, "<h1>Cited cases</h1>", html=False)
        self.assertNotContains(response, "Advanced search")
        self.assertContains(response, "Citation")
        self.assertContains(response, "Judgment date")
        self.assertContains(response, self.second_judgment.title)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.unrelated_judgment.title)
        self.assertContains(response, 'placeholder="Filter documents"', html=False)

    def test_law_report_volume_detail_view_legislation_tab(self):
        url = reverse(
            "law_report_volume_legislation_index",
            args=[self.law_report.slug, self.volume_1.slug],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "peachjam/law_report/law_report_volume_legislation_index.html"
        )
        self.assertEqual("legislation", response.context["active_tab"])
        self.assertTrue(response.context.get("doc_table_toggle"))
        self.assertContains(
            response,
            reverse("user_following_button") + f"?law_report={self.law_report.pk}",
        )
        self.assertContains(
            response, '<h1 class="mb-0">East Africa Law Reports</h1>', html=False
        )
        self.assertContains(response, '<h2 class="h4 mb-0">Volume 1</h2>', html=False)
        self.assertNotContains(response, "<h1>Cited legislation</h1>", html=False)
        self.assertNotContains(response, "Advanced search")
        self.assertContains(response, self.cited_legislation.title, count=1)
        self.assertContains(response, self.first_judgment.title)
        self.assertNotContains(response, self.other_legislation.title)
        legislation_row = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "work_id", None) == self.cited_legislation.work_id
        )
        self.assertEqual(self.latest_cited_legislation.pk, legislation_row.pk)
        self.assertEqual(self.latest_cited_legislation.date, legislation_row.date)
        self.assertNotEqual(self.original_cited_legislation_date, legislation_row.date)
        self.assertContains(response, 'placeholder="Filter documents"', html=False)

    def test_law_report_volume_detail_view_ignores_tab_query_param(self):
        url = self.volume_1.get_absolute_url() + "?tab=invalid"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual("judgments", response.context["active_tab"])
