import os

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

        form = self.app.get(judgment_add_url).forms["judgment_form"]

        form["jurisdiction"] = "ZA"
        form["court"] = "1"
        form["language"] = "en"
        form["case_name"] = "test case"

        # date uses a multi-field widget
        form["date_0"] = "21"
        form["date_1"] = "2"
        form["date_2"] = "2000"

        with open(
            os.path.abspath("peachjam/fixtures/source_files/zagpjhc_judgment.docx"),
            "rb",
        ) as docx_file:
            docx_file_content = docx_file.read()

        # upload file
        form["upload_file"] = Upload(
            "file.docx",
            docx_file_content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = form.submit()
        self.assertRedirects(response, judgment_list_url)

        judgment = Judgment.objects.filter(
            expression_frbr_uri="/akn/za/judgment/eacj/2000/1/eng@2000-02-21"
        ).first()
        self.assertIsNotNone(judgment)

        # check if content_html has been extracted
        self.assertIn(
            "The second count is robbery, in that on or about near the place mentioned in count",
            judgment.content_html,
        )
        self.assertEqual(
            "file.docx",
            judgment.source_file.filename,
        )

        # swap source file with pdf
        judgment_change_url = reverse(
            "admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk}
        )
        form2 = self.app.get(judgment_change_url).forms["judgment_form"]

        with open(
            os.path.abspath("peachjam/fixtures/source_files/gauteng_judgment.pdf"), "rb"
        ) as pdf_file:
            pdf_file_content = pdf_file.read()
        form2["source_file-0-file"] = Upload(
            "upload_pdf.pdf", pdf_file_content, "application/pdf"
        )
        response2 = form2.submit()
        self.assertRedirects(response2, judgment_list_url)

        judgment.refresh_from_db()
        self.assertEqual("upload_pdf.pdf", judgment.source_file.filename)

    def test_add_judgment_pdf_swap_docx(self):
        # add judgment
        judgment_add_url = reverse("admin:peachjam_judgment_add")
        judgment_list_url = reverse("admin:peachjam_judgment_changelist")

        form = self.app.get(judgment_add_url).forms["judgment_form"]

        form["jurisdiction"] = "ZA"
        form["court"] = "1"
        form["language"] = "en"
        form["case_name"] = "test case"

        # date uses a multi-field widget
        form["date_0"] = "25"
        form["date_1"] = "3"
        form["date_2"] = "1999"

        # upload file
        with open(
            os.path.abspath("peachjam/fixtures/source_files/gauteng_judgment.pdf"), "rb"
        ) as pdf_file:
            pdf_file_content = pdf_file.read()

        form["upload_file"] = Upload(
            "upload_pdf.pdf", pdf_file_content, "application/pdf"
        )

        response = form.submit()
        self.assertRedirects(response, judgment_list_url)

        judgment = Judgment.objects.filter(
            expression_frbr_uri="/akn/za/judgment/eacj/1999/1/eng@1999-03-25"
        ).first()
        self.assertIsNotNone(judgment)

        # check if content_html has been extracted
        self.assertEqual(
            "upload_pdf.pdf",
            judgment.source_file.filename,
        )

        # swap source file with pdf
        judgment_change_url = reverse(
            "admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk}
        )

        with open(
            os.path.abspath("peachjam/fixtures/source_files/zagpjhc_judgment.docx"),
            "rb",
        ) as docx_file:
            docx_file_content = docx_file.read()

        form2 = self.app.get(judgment_change_url).forms["judgment_form"]
        form2["source_file-0-file"] = Upload(
            "file.docx",
            docx_file_content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response2 = form2.submit()
        self.assertRedirects(response2, judgment_list_url)

        judgment.refresh_from_db()
        self.assertIn(
            "The second count is robbery, in that on or about near the place mentioned in count",
            judgment.content_html,
        )
        self.assertEqual("file.docx", judgment.source_file.filename)
