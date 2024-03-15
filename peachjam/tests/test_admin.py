from django.contrib.auth.models import User
from django.urls import reverse
from django_webtest import WebTest
from webtest import Upload

from peachjam.models import Judgment


class TestJudgmentAdmin(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.app.set_user(User.objects.get(username="admin@example.com"))

    def test_add_judgment_docx_swap_pdf(self):
        # add judgment
        judgment_add_url = reverse("admin:peachjam_judgment_add")
        judgment_list_url = reverse("admin:peachjam_judgment_changelist")

        form = self.app.get(judgment_add_url).form

        form["jurisdiction"] = "ZA"
        form["court"] = "1"
        form["language"] = "en"
        form["case_name"] = "test case"

        # date uses a multi-field widget
        form["date_0"] = "21"
        form["date_1"] = "2"
        form["date_2"] = "2000"

        # upload file
        form["upload_file"] = Upload(
            "file.docx",
            b"test case file judgment details",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = form.submit()
        self.assertRedirects(response, judgment_list_url)

        judgment = Judgment.objects.filter(
            expression_frbr_uri="/akn/za/judgment/eacj/2000/1/eng@2000-02-21"
        ).first()
        self.assertIsNotNone(judgment)

        # check if content_html has been extracted
        self.assertIn("test case", judgment.content_html)
        self.assertEqual(
            "test-case-2000-eacj-1-21-february-2000.docx",
            judgment.source_file.filename,
        )

        # swap source file with pdf
        judgment_change_url = reverse(
            "admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk}
        )
        form2 = self.app.get(judgment_change_url).form
        form2["source_file-0-file"] = Upload(
            "upload_pdf.pdf", b"pdf judgment content", "application/pdf"
        )
        response2 = form2.submit()
        self.assertRedirects(response2, judgment_list_url)

        judgment.refresh_from_db()
        self.assertEqual(
            "test-case-2000-eacj-1-21-february-2000.pdf", judgment.source_file.filename
        )

    def test_add_judgment_pdf_swap_docx(self):
        # add judgment
        judgment_add_url = reverse("admin:peachjam_judgment_add")
        judgment_list_url = reverse("admin:peachjam_judgment_changelist")

        form = self.app.get(judgment_add_url).form

        form["jurisdiction"] = "ZA"
        form["court"] = "1"
        form["language"] = "en"
        form["case_name"] = "test case"

        # date uses a multi-field widget
        form["date_0"] = "25"
        form["date_1"] = "3"
        form["date_2"] = "1999"

        # upload file

        raw_pdf_data = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<< /Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<< /Type /Page\n/Parent 2 0 R\n/Contents 4 0 R\n/MediaBox [0 0 612 792]\n/Resources << /ProcSet 5 0 R\n/Font << /F1 6 0 R\n>>\n>>\nendobj\n4 0 obj\n<< /Length 5 0 R\n>>\nstream\nBT\n/F1 24 Tf\n100 700 Td\n(Hello, World!) Tj\nET\nendstream\nendobj\n5 0 obj\n32\nendobj\n6 0 obj\n<< /Type /Font\n/Subtype /Type1\n/Name /F1\n/BaseFont /Helvetica\n/Encoding /WinAnsiEncoding\n>>\nendobj\nxref\n0 7\n0000000000 65535 f\n0000000009 00000 n\n0000000078 00000 n\n0000000171 00000 n\n0000000260 00000 n\n0000000315 00000 n\n0000000389 00000 n\ntrailer\n<< /Size 7\n/Root 1 0 R\n>>\nstartxref\n477\n%%EOF\n"  # noqa
        form["upload_file"] = Upload("upload_pdf.pdf", raw_pdf_data, "application/pdf")

        response = form.submit()
        self.assertRedirects(response, judgment_list_url)

        judgment = Judgment.objects.filter(
            expression_frbr_uri="/akn/za/judgment/eacj/1999/1/eng@1999-03-25"
        ).first()
        self.assertIsNotNone(judgment)

        # check if content_html has been extracted
        self.assertEqual(
            "test-case-1999-eacj-1-25-march-1999.pdf",
            judgment.source_file.filename,
        )

        # swap source file with pdf
        judgment_change_url = reverse(
            "admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk}
        )
        form2 = self.app.get(judgment_change_url).form
        form2["source_file-0-file"] = Upload(
            "file.docx",
            b"test case file judgment details",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response2 = form2.submit()
        self.assertRedirects(response2, judgment_list_url)

        judgment.refresh_from_db()
        self.assertIn("test case", judgment.content_html)
        self.assertEqual(
            "test-case-1999-eacj-1-25-march-1999.docx", judgment.source_file.filename
        )
