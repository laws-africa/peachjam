from tempfile import NamedTemporaryFile
from unittest import mock

import tablib
from django.test import TestCase

from peachjam.models import Judgment
from peachjam.resources import JudgmentResource

judgment_import_headers = [
    "case_name",
    "case_numbers",
    "case_string_override",
    "court",
    "source_url",
    "mnc",
    "serial_number",
    "date",
    "jurisdiction",
    "language",
    "judges",
    "media_summary_file",
]
row = [
    "Sigcau and Another v President of Republic of South Africa and Others",
    "961/2020|961/2021",
    "",
    "East African Court of Justice",
    "https://mediafile.pdf|https://mediafile.docx",
    "[2022] ZASCA 121",
    "44",
    "2022-09-14",
    "ZA",
    "eng",
    "Maya P|Dambuza JA|Makgoka JA|Gorven JA|Makaula AJA",
    "",
]


class JudgmentBulkImportTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]

    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_source_file_prefers_docx_over_pdf(self, mock_download):
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        JudgmentResource().import_data(dataset, dry_run=False)
        mock_download.assert_called_with(row[4].split("|")[1])

    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_case_number_import_without_matter_type(self, mock_download):
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        result = JudgmentResource().import_data(dataset, dry_run=False)
        j = Judgment.objects.filter(case_name=row[0]).first()
        case_numbers = j.case_numbers.all()
        self.assertFalse(result.has_errors())
        self.assertEqual(case_numbers[0].number, 961)

    @mock.patch(
        "peachjam.resources.download_source_file", return_value=NamedTemporaryFile()
    )
    def test_case_numbers_with_matter_type(self, mock_download):
        row[1] = "961/2002/Application|260/2003/Application"
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        result = JudgmentResource().import_data(dataset, dry_run=False)
        j = Judgment.objects.filter(case_name=row[0]).first()
        case_numbers = j.case_numbers.all()
        self.assertFalse(result.has_errors())
        self.assertEqual(case_numbers[0].matter_type.name, "Application")
