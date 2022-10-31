import tablib
from django.test import TestCase

from peachjam.resources import JudgmentResource

judgment_import_headers = [
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
]
row = [
    "Sigcau and Another v President of Republic of South Africa and Others",
    "CCT 315/21|CCT 321/21|CCT 6/22",
    "315|321|6",
    "2021|2021|2022",
    "East African Court of Justice",
    "https://mediafile.pdf|https://mediafile.docx",
    "[2022] ZASCA 121",
    "44",
    "2022-09-14",
    "ZA",
    "eng",
    "Maya P|Dambuza JA|Makgoka JA|Gorven JA|Makaula AJA",
    "",
    "",
]


class JudgmentBulkImportTestCase(TestCase):
    fixtures = ["tests/courts", "tests/countries", "tests/languages"]

    def test_source_file_prefers_docx_over_pdf(self):
        dataset = tablib.Dataset(row, headers=judgment_import_headers)
        source_url = JudgmentResource().get_source_url(dataset.dict[0])
        self.assertEqual(source_url, row[4].split("|")[1])

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
