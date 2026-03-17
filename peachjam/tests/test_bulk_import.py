from tempfile import NamedTemporaryFile
from unittest import mock

import tablib
from django.contrib.auth.models import User
from django.test import TestCase

from peachjam.models import GenericDocument, Judgment, Offence, Taxonomy, Work
from peachjam.resources import (
    GenericDocumentResource,
    JudgmentResource,
    OffenceResource,
)

judgment_import_headers = [
    "skip",
    "case_name",
    "case_string_override",
    "case_number_numeric",
    "case_number_year",
    "court",
    "source_url",
    "mnc",
    "serial_number",
    "date",
    "jurisdiction",
    "language",
    "judges",
    "media_summary_file",
    "matter_type",
    "serial_number_override",
]
row = [
    "",
    "Sigcau and Another v President of Republic of South Africa and Others",
    "CCT 315/21|CCT 321/21|CCT 6/22",
    "315|321|6",
    "2021|2021|2021",
    "EACJ",
    "https://example.com/mediafile.pdf|https://example.com/mediafile.docx",
    "[2022] EACJ 121",
    "44",
    "2022-09-14",
    "ZA",
    "eng",
    "Maya P|Dambuza JA|Makgoka JA|Gorven JA|Makaula AJA",
    "",
    "",
    "121",
]


def mocked_response(*args, **kwargs):
    class MockResponse:
        def __init__(self, data, status_code):
            self.data = data
            self.status_code = status_code
            self.content = b""

        def raise_for_status(self):
            pass

    return MockResponse(None, 200)


class JudgmentBulkImportTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages", "tests/users"]

    @mock.patch("peachjam.resources.requests.get", side_effect=mocked_response)
    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_source_file_prefers_docx_over_pdf(self, mock_request, mock_download):
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        result = JudgmentResource().import_data(dataset=dataset, dry_run=False)
        j = Judgment.objects.get(mnc="[2022] EACJ 121")
        self.assertFalse(result.has_errors())
        self.assertEqual(j.source_url, "https://example.com/mediafile.docx")

    def test_case_number_import_without_matter_type(self):
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        case_numbers = JudgmentResource().get_case_numbers(dataset.dict[0])
        self.assertEqual(case_numbers[0].number, 315)

    def test_case_numbers_with_matter_type(self):
        row.append("CCT|CCT|CCT")
        judgment_import_headers.append("matter_type")
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        case_numbers = JudgmentResource().get_case_numbers(dataset.dict[0])
        self.assertEqual(case_numbers[0].matter_type.name, "CCT")

    @mock.patch("peachjam.resources.requests.get", side_effect=mocked_response)
    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_judgment_bulk_import(self, mock_request, download):
        user = User.objects.first()
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        result = JudgmentResource().import_data(
            dataset=dataset, dry_run=False, user=user
        )
        judgment = Judgment.objects.first()
        self.assertFalse(result.has_errors())
        self.assertEqual(judgment.case_numbers.first().year, 2021)
        self.assertEqual(judgment.created_by, user)

    @mock.patch("peachjam.resources.requests.get", side_effect=mocked_response)
    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_import_with_taxonomy(self, mock_request, download):
        data = row[:]
        headers = judgment_import_headers[:]

        get = lambda node_id: Taxonomy.objects.get(pk=node_id)  # noqa
        root = Taxonomy.add_root(name="Collections")
        node = get(root.pk).add_child(name="Land Rights")
        get(node.pk).add_sibling(name="Environment")

        data.append("collections-land-rights|collections-environment")
        headers.append("taxonomies")
        dataset = tablib.Dataset(data, headers=headers, depth=0)
        result = JudgmentResource().import_data(dataset=dataset, dry_run=False)
        self.assertFalse(result.has_errors())
        self.assertEqual([], result.invalid_rows)
        j = Judgment.objects.first()
        self.assertEqual(len(j.taxonomies.all()), 2)

    def test_generic_document_import(self):
        headers = [
            "skip",
            "jurisdiction",
            "date",
            "language",
            "nature",
            "title",
            "frbr_uri_doctype",
        ]
        row = ["", "ZA", "2022-09-14", "eng", "thing", "a test", "doc"]

        dataset = tablib.Dataset(row, headers=headers)
        result = GenericDocumentResource().import_data(dataset=dataset, dry_run=False)
        self.assertEqual([], result.invalid_rows)
        self.assertFalse(result.has_errors())
        d = GenericDocument.objects.first()
        self.assertEqual("/akn/za/doc/thing/2022-09-14/a-test", d.work_frbr_uri)

    def test_frbr_uri_date(self):
        headers = [
            "skip",
            "jurisdiction",
            "date",
            "language",
            "nature",
            "title",
            "frbr_uri_doctype",
            "frbr_uri_date",
        ]
        row = ["", "ZA", "2022-09-14", "eng", "thing", "a test", "doc", 2019]

        dataset = tablib.Dataset(row, headers=headers)
        result = GenericDocumentResource().import_data(dataset=dataset, dry_run=False)
        self.assertEqual([], result.invalid_rows)
        self.assertFalse(result.has_errors())
        d = GenericDocument.objects.first()
        self.assertEqual("/akn/za/doc/thing/2019/a-test", d.work_frbr_uri)

    def test_empty_row(self):
        headers = [
            "skip",
            "jurisdiction",
            "date",
            "language",
            "nature",
            "title",
            "frbr_uri_doctype",
            "frbr_uri_date",
        ]
        row = ["", "", "", "", "", None, "", None]

        dataset = tablib.Dataset(row, headers=headers)
        result = GenericDocumentResource().import_data(dataset=dataset, dry_run=False)
        self.assertEqual([], result.invalid_rows)
        self.assertFalse(result.has_errors())
        self.assertEqual(0, result.totals["new"])
        self.assertEqual(0, result.totals["update"])
        self.assertEqual(1, result.totals["skip"])
        self.assertIsNone(GenericDocument.objects.first())

    def test_source_html_import_export_round_trip(self):
        headers = [
            "skip",
            "jurisdiction",
            "date",
            "language",
            "nature",
            "title",
            "frbr_uri_doctype",
            "source_html",
        ]
        row = [
            "",
            "ZA",
            "2022-09-14",
            "eng",
            "thing",
            "source html round trip",
            "doc",
            "<h1>Heading</h1><p>Body</p>",
        ]

        resource = GenericDocumentResource()
        result = resource.import_data(
            dataset=tablib.Dataset(row, headers=headers), dry_run=False
        )
        self.assertFalse(result.has_errors())

        doc = GenericDocument.objects.get(title="source html round trip")
        self.assertEqual(
            "<h1>Heading</h1><p>Body</p>", doc.document_content.source_html
        )
        self.assertIn("Body", doc.document_content.content_html)

        exported = resource.export(GenericDocument.objects.filter(pk=doc.pk))
        self.assertIn("source_html", exported.headers)
        self.assertNotIn("content_html", exported.headers)
        self.assertEqual("<h1>Heading</h1><p>Body</p>", exported.dict[0]["source_html"])

    def test_content_html_import_is_legacy_fallback_with_warning(self):
        headers = [
            "skip",
            "jurisdiction",
            "date",
            "language",
            "nature",
            "title",
            "frbr_uri_doctype",
            "content_html",
        ]
        row = [
            "",
            "ZA",
            "2022-09-15",
            "eng",
            "thing",
            "legacy html fallback",
            "doc",
            "<p>Legacy content_html value</p>",
        ]

        with self.assertLogs("peachjam.resources", level="WARNING") as captured:
            result = GenericDocumentResource().import_data(
                dataset=tablib.Dataset(row, headers=headers), dry_run=False
            )

        self.assertFalse(result.has_errors())
        self.assertTrue(
            any(
                "Deprecated import header 'content_html'" in line
                for line in captured.output
            )
        )
        self.assertTrue(
            any(
                "Deprecated import column 'content_html'" in line
                for line in captured.output
            )
        )
        doc = GenericDocument.objects.get(title="legacy html fallback")
        self.assertEqual(
            "<p>Legacy content_html value</p>", doc.document_content.source_html

class OffenceBulkImportTestCase(TestCase):
    def setUp(self):
        self.work = Work.objects.create(
            title="Penal Code",
            frbr_uri="/akn/tz/act/2002/16",
        )

    def test_offence_import(self):
        headers = [
            "work",
            "provision_eid",
            "code",
            "title",
            "description",
            "elements",
            "penalty",
        ]
        row = [
            self.work.frbr_uri,
            "sec_296",
            "ROB-296",
            "Robbery with violence",
            "The accused steals while armed with a dangerous weapon.",
            "stealing property|armed with a dangerous weapon",
            "Imprisonment for life",
        ]

        dataset = tablib.Dataset(row, headers=headers)
        result = OffenceResource().import_data(dataset=dataset, dry_run=False)

        self.assertEqual([], result.invalid_rows)
        self.assertFalse(result.has_errors())

        offence = Offence.objects.get(code="ROB-296")
        self.assertEqual(self.work, offence.work)
        self.assertEqual(
            ["stealing property", "armed with a dangerous weapon"], offence.elements
        )

    def test_offence_export(self):
        offence = Offence.objects.create(
            work=self.work,
            provision_eid="sec_296",
            code="ROB-296",
            title="Robbery with violence",
            description="The accused steals while armed with a dangerous weapon.",
            elements=["stealing property", "armed with a dangerous weapon"],
            penalty="Imprisonment for life",
        )

        dataset = OffenceResource().export(Offence.objects.filter(pk=offence.pk))

        self.assertEqual(self.work.frbr_uri, dataset.dict[0]["work"])
        self.assertEqual(
            "stealing property|armed with a dangerous weapon",
            dataset.dict[0]["elements"],
        )
