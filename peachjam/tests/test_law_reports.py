import datetime
from copy import deepcopy

from countries_plus.models import Country
from django.test import TestCase
from django.urls import reverse
from languages_plus.models import Language

from peachjam.models import (
    Court,
    ExtractedCitation,
    Judgment,
    Label,
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
        reported_label, _ = Label.objects.get_or_create(
            code="reported",
            defaults={"name": "Reported", "level": "success"},
        )
        self.first_judgment.labels.add(reported_label)
        self.second_judgment.labels.add(reported_label)
        self.second_judgment.labels.add(Label.objects.create(name="Featured case"))
        self.cited_legislation = Legislation.objects.get(
            expression_frbr_uri=(
                "/akn/aa-au/act/1969/civil-aviation-commission/eng@1969-01-17"
            )
        )
        self.other_legislation = Legislation.objects.get(
            expression_frbr_uri=(
                "/akn/aa-au/act/pact/2005/non-aggression-and-common-defence/eng@2005-01-31"
            )
        )
        self.original_cited_legislation_date = self.cited_legislation.date
        self.latest_cited_legislation = Legislation.objects.create(
            jurisdiction=self.cited_legislation.jurisdiction,
            locality=self.cited_legislation.locality,
            title=self.cited_legislation.title,
            date=self.cited_legislation.date + datetime.timedelta(days=365),
            source_url=self.cited_legislation.source_url,
            citation=self.cited_legislation.citation,
            metadata_json=deepcopy(self.cited_legislation.metadata_json),
            language=self.cited_legislation.language,
            frbr_uri_doctype=self.cited_legislation.frbr_uri_doctype,
            frbr_uri_subtype=self.cited_legislation.frbr_uri_subtype,
            frbr_uri_actor=self.cited_legislation.frbr_uri_actor,
            frbr_uri_date=self.cited_legislation.frbr_uri_date,
            frbr_uri_number=self.cited_legislation.frbr_uri_number,
            allow_robots=self.cited_legislation.allow_robots,
            published=self.cited_legislation.published,
            timeline_json=deepcopy(self.cited_legislation.timeline_json),
            commencements_json=deepcopy(self.cited_legislation.commencements_json),
            repealed=self.cited_legislation.repealed,
            parent_work=self.cited_legislation.parent_work,
            principal=self.cited_legislation.principal,
        )
        self.assertEqual(
            self.cited_legislation.work_id, self.latest_cited_legislation.work_id
        )
        self.assertEqual(
            self.cited_legislation.work_frbr_uri,
            self.latest_cited_legislation.work_frbr_uri,
        )

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
        self.assertContains(response, 'class="row row-cols-1 row-cols-md-auto g-4"')
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
            [[self.volume_2, self.volume_1]],
            response.context["law_report_volume_columns"],
        )
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
        self.assertContains(response, "Reported judgments")
        self.assertFalse(response.context.get("doc_table_toggle"))
        self.assertNotContains(
            response, 'class="doc-table-children collapse"', html=False
        )
        self.assertNotContains(response, 'title="Cited by"', html=False)
        self.assertNotContains(response, "1 cited case")
        self.assertNotContains(
            response, '<span class="badge rounded-pill bg-success">Reported</span>'
        )
        self.assertNotIn("labels", response.context["facet_data"])
        self.assertEqual(self.volume_1, response.context["law_report_volume"])
        self.assertEqual("judgments", response.context["active_tab"])
        parent_row = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "work_id", None) == self.first_judgment.work_id
        )
        self.assertFalse(hasattr(parent_row, "children"))
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
        self.assertEqual("Cited by", response.context.get("doc_table_toggle_title"))
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
        self.assertContains(response, "Reported judgments")
        self.assertNotContains(response, "1 reported judgment")
        self.assertContains(response, "Cited by 1 judgment")
        self.assertIn("labels", response.context["facet_data"])
        self.assertIn("alphabet", response.context["facet_data"])
        self.assertContains(response, 'class="doc-table-children collapse show"')
        self.assertContains(response, 'title="Cited by"', html=False)
        self.assertContains(response, "Cited by 1 judgment")
        self.assertNotContains(
            response, '<span class="badge rounded-pill bg-success">Reported</span>'
        )
        self.assertNotIn(
            ("Reported", "Reported"),
            response.context["facet_data"]["labels"]["options"],
        )
        parent_row = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "work_id", None) == self.second_judgment.work_id
        )
        child_row = parent_row.children[0]
        self.assertEqual(self.first_judgment.work_id, child_row.work_id)
        self.assertTrue(child_row.is_table_child)
        self.assertEqual("Cited by 1 judgment", parent_row.children_group_row["title"])
        self.assertContains(
            response, f"saved-document-star--{self.first_judgment.pk}", count=1
        )
        self.assertIn("work", child_row._state.fields_cache)
        self.assertIn("labels", child_row._prefetched_objects_cache)
        self.assertIn("taxonomies", child_row._prefetched_objects_cache)
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
        self.assertEqual("Cited by", response.context.get("doc_table_toggle_title"))
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
        self.assertContains(response, "Reported judgments")
        self.assertNotContains(response, "1 reported judgment")
        self.assertContains(response, "Cited by 1 judgment")
        self.assertIn("years", response.context["facet_data"])
        self.assertIn("alphabet", response.context["facet_data"])
        self.assertFalse(response.context.get("doc_table_show_doc_type"))
        self.assertTrue(response.context.get("doc_table_full_title_width"))
        self.assertNotContains(
            response, '<span class="badge rounded-pill bg-success">Reported</span>'
        )
        legislation_row = next(
            doc
            for doc in response.context["documents"]
            if getattr(doc, "work_id", None) == self.cited_legislation.work_id
        )
        self.assertEqual(self.latest_cited_legislation.pk, legislation_row.pk)
        self.assertEqual(self.latest_cited_legislation.date, legislation_row.date)
        self.assertNotEqual(self.original_cited_legislation_date, legislation_row.date)
        child_row = legislation_row.children[0]
        self.assertTrue(child_row.is_table_child)
        self.assertEqual(
            "Cited by 1 judgment", legislation_row.children_group_row["title"]
        )
        self.assertContains(
            response, f"saved-document-star--{self.first_judgment.pk}", count=1
        )
        self.assertContains(response, 'class="doc-table-children collapse show"')
        self.assertContains(response, 'title="Cited by"', html=False)
        self.assertContains(response, "Cited by 1 judgment")
        self.assertContains(response, 'placeholder="Filter documents"', html=False)

    def test_law_report_volume_detail_view_ignores_tab_query_param(self):
        url = self.volume_1.get_absolute_url() + "?tab=invalid"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual("judgments", response.context["active_tab"])
