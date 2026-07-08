import io
import shutil
import zipfile
from unittest import skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from peachjam.book_word import (
    DOCX_MIMETYPE,
    BookWordError,
    _markdown_headings_option,
    analyse_markdown,
    docx_to_markdown,
    extract_headings,
    html_diff_headings,
    markdown_to_docx,
    protect_law_widgets,
    restore_law_widgets,
    validate_docx,
)


class BookWordConversionTest(SimpleTestCase):
    def test_protect_law_widgets(self):
        markdown = (
            '<la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~sec_1" '
            'fetch partner="laws.africa">'
        )

        self.assertEqual(
            'XX-la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~sec_1" '
            'fetch partner="laws.africa">',
            protect_law_widgets(markdown),
        )

    def test_restore_law_widgets_only_unescapes_widget_lines(self):
        markdown = (
            "This keeps an escaped \\_ outside widgets.\n\n"
            'XX-la-akoma-ntoso frbr-expression-uri=\\"/akn/bw/act/1967/8/eng/\\~part_I\\_\\_sec_2\\" '
            'fetch partner=\\"laws.africa\\"\\>'
        )

        self.assertEqual(
            "This keeps an escaped \\_ outside widgets.\n\n"
            '<la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~part_I__sec_2" '
            'fetch partner="laws.africa">',
            restore_law_widgets(markdown),
        )

    def test_analyse_markdown_counts_import_blockers(self):
        analysis = analyse_markdown(
            "# Heading\n\n"
            '<la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~sec_1" fetch partner="laws.africa">\n'
            'XX-la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~sec_2">\n'
            "![Chart](media/image1.png)"
        )

        self.assertEqual(1, analysis.heading_count)
        self.assertEqual(1, analysis.law_widget_count)
        self.assertEqual(1, analysis.protected_law_widget_count)
        self.assertEqual(1, analysis.image_count)

    def test_analyse_markdown_counts_setext_headings(self):
        analysis = analyse_markdown("Heading\n=======\n\nSubheading\n----------\n")

        self.assertEqual(2, analysis.heading_count)

    def test_extract_headings_normalises_pandoc_attributes(self):
        headings = extract_headings(
            "# 1. Title {#title .unnumbered}\n\n" "2. Subtitle\n" "-----------\n"
        )

        self.assertEqual(["h1 1. Title", "h2 2. Subtitle"], [h.label for h in headings])

    def test_html_diff_headings_reports_heading_changes(self):
        html = html_diff_headings(
            "# 1. Current\n\n## 1.1 Removed\n\n# 2. Same\n",
            "# 1. Imported\n\n# 2. Same\n\n## 2.1 Added\n",
        )

        self.assertIn('class="diff"', html)
        self.assertIn("diff_chg", html)
        self.assertIn("diff_sub", html)
        self.assertIn("diff_add", html)

    def test_html_diff_headings_escapes_heading_text(self):
        html = html_diff_headings("# Heading <script>\n", "# Heading changed\n")

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_html_diff_headings_is_empty_without_heading_changes(self):
        self.assertEqual("", html_diff_headings("# Same\n", "# Same\n"))

    def test_markdown_headings_option_requests_atx_headings(self):
        self.assertIn(
            _markdown_headings_option(),
            ["--markdown-headings=atx", "--atx-headers"],
        )

    def test_validate_docx_rejects_comments(self):
        uploaded = SimpleUploadedFile(
            "book.docx",
            self.make_docx(
                {
                    "word/comments.xml": b"<w:comments><w:comment w:id='1' /></w:comments>"
                }
            ),
            content_type=DOCX_MIMETYPE,
        )

        with self.assertRaisesRegex(BookWordError, "comments"):
            validate_docx(uploaded)

    def test_validate_docx_rejects_tracked_changes(self):
        uploaded = SimpleUploadedFile(
            "book.docx",
            self.make_docx(
                {"word/document.xml": b"<w:document><w:ins /></w:document>"}
            ),
            content_type=DOCX_MIMETYPE,
        )

        with self.assertRaisesRegex(BookWordError, "tracked changes"):
            validate_docx(uploaded)

    @skipUnless(shutil.which("pandoc"), "pandoc is required")
    def test_docx_round_trip_restores_law_widgets(self):
        markdown = (
            "# Heading\n\n"
            "Body\n\n"
            '<la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~part_I__sec_2" '
            'fetch partner="laws.africa">'
        )
        docx = markdown_to_docx(markdown)
        uploaded = SimpleUploadedFile("book.docx", docx, content_type=DOCX_MIMETYPE)

        imported = docx_to_markdown(uploaded)

        self.assertIn("# Heading", imported)
        self.assertIn(
            '<la-akoma-ntoso frbr-expression-uri="/akn/bw/act/1967/8/eng/~part_I__sec_2" '
            'fetch partner="laws.africa">',
            imported,
        )
        self.assertNotIn("XX-la-akoma-ntoso", imported)

    def make_docx(self, overrides=None):
        files = {
            "[Content_Types].xml": b"<Types></Types>",
            "word/document.xml": b"<w:document></w:document>",
        }
        files.update(overrides or {})

        f = io.BytesIO()
        with zipfile.ZipFile(f, "w") as docx:
            for name, content in files.items():
                docx.writestr(name, content)
        return f.getvalue()
