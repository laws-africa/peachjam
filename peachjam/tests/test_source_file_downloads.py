from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from peachjam.adapters.indigo import IndigoAdapter
from peachjam.models import SourceFile
from peachjam.views.generic_views import BaseDocumentDetailView


class SourceFileDownloadsTest(SimpleTestCase):
    def test_pdf_download_label_for_existing_quoted_filenames(self):
        for filename in ("document.pdf", '"document.pdf"', 'document.pdf"'):
            with self.subTest(filename=filename):
                source_file = SourceFile(filename=filename, size=1024)
                view = BaseDocumentDetailView()
                view.object = SimpleNamespace(
                    source_file=source_file,
                    expression_frbr_uri="/akn/za/act/2024/1/eng@2024-01-01",
                )
                options = view.get_download_options()
                self.assertEqual(source_file.filename_extension(), "pdf")
                self.assertEqual(len(options), 1)
                self.assertEqual(options[0]["label"], "PDF")
                html = render_to_string(
                    "peachjam/_document_detail_toolbar.html",
                    {"download_options": options},
                )
                self.assertIn("Download PDF", html)
                self.assertNotIn("PDF&quot;", html)
                self.assertNotIn("dropdown-toggle-split", html)

    def test_other_source_formats_keep_pdf_option(self):
        view = BaseDocumentDetailView()
        view.object = SimpleNamespace(
            source_file=SourceFile(filename="document.docx", size=1024),
            expression_frbr_uri="/akn/za/act/2024/1/eng@2024-01-01",
        )
        self.assertEqual(
            [option["label"] for option in view.get_download_options()],
            ["DOCX", "PDF"],
        )

    @patch("peachjam.adapters.indigo.magic.from_file", return_value="application/pdf")
    @patch.object(SourceFile, "save")
    @patch.object(SourceFile, "track_changes")
    def test_import_source_filename_from_download_header(
        self, track_changes, save, mime
    ):
        adapter = IndigoAdapter(
            None, {"token": "XXX", "api_url": "http://example.com", "places": "za"}
        )
        cases = [
            (
                {"Content-Disposition": 'attachment; filename="document.pdf"'},
                "document.pdf",
            ),
            (
                {"Content-Disposition": "attachment; filename=document.pdf"},
                "document.pdf",
            ),
            (
                {
                    "Content-Disposition": 'attachment; filename="document.pdf"; size=123'
                },
                "document.pdf",
            ),
            (
                {
                    "Content-Disposition": "attachment; filename*=UTF-8''document%20name.pdf"
                },
                "document name.pdf",
            ),
            ({"Content-Disposition": "attachment"}, "fixture-pdf.pdf"),
            ({}, "fixture-pdf.pdf"),
        ]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                source_file = SourceFile()
                adapter.client_get = lambda url: SimpleNamespace(
                    content=b"PDF", headers=headers
                )
                adapter.download_source_file(
                    "http://example.com/source.pdf",
                    SimpleNamespace(source_file=source_file),
                    "Fixture PDF",
                )
                self.assertEqual(source_file.file.name, expected)
