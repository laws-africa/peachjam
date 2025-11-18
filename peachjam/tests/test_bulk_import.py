from tempfile import NamedTemporaryFile
from unittest import mock

import tablib
from django.contrib.auth.models import User
from django.test import TestCase

from peachjam.models import GenericDocument, Judgment, Taxonomy
from peachjam.resources import GenericDocumentResource, JudgmentResource

judgment_import_headers = [
    "expression_frbr_uri",
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
    "/akn/za/judgment/eacj/2022/44/eng@2022-09-14",
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
        self.assertEquals(judgment.case_numbers.first().year, 2021)
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
