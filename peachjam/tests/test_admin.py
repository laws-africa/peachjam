import os
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django_webtest import WebTest
from webtest import Upload

from peachjam.models import (
    Country,
    GenericDocument,
    Journal,
    JournalArticle,
    Judgment,
    Language,
    SourceFile,
    VolumeIssue,
)


class TestJudgmentAdmin(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/courts", "tests/languages"]

    def setUp(self):
        self.app.set_user(User.objects.get(username="admin@example.com"))

    def make_judgment(self, anonymised=False):
        return Judgment.objects.create(
            case_name="Warning test case",
            court_id=1,
            date=date(2026, 1, 8),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
            anonymised=anonymised,
        )

    def attach_source_file(self, judgment, file_is_anonymised):
        with open(
            os.path.abspath("peachjam/fixtures/source_files/gauteng_judgment.pdf"), "rb"
        ) as pdf_file:
            return SourceFile.objects.create(
                document=judgment,
                file=SimpleUploadedFile(
                    "warning-source.pdf",
                    pdf_file.read(),
                    content_type="application/pdf",
                ),
                filename="warning-source.pdf",
                mimetype="application/pdf",
                file_is_anonymised=file_is_anonymised,
            )

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
            judgment.document_content.content_html,
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
            judgment.document_content.content_html,
        )
        self.assertEqual("file.docx", judgment.source_file.filename)

    def test_change_form_warns_if_anonymised_judgment_source_file_is_not_marked_anonymised(
        self,
    ):
        judgment = self.make_judgment(anonymised=True)
        self.attach_source_file(judgment, file_is_anonymised=False)

        response = self.app.get(
            reverse("admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk})
        )

        self.assertIn(
            "This judgment is marked as anonymised, but the attached source file is not marked as anonymised.",
            response.text,
        )

    def test_change_form_does_not_warn_when_attached_source_file_is_marked_anonymised(
        self,
    ):
        judgment = self.make_judgment(anonymised=True)
        self.attach_source_file(judgment, file_is_anonymised=True)

        response = self.app.get(
            reverse("admin:peachjam_judgment_change", kwargs={"object_id": judgment.pk})
        )

        self.assertNotIn(
            "This judgment is marked as anonymised, but the attached source file is not marked as anonymised.",
            response.text,
        )

    def test_dup_files_check(self):
        judgment = self.make_judgment(anonymised=True)
        self.attach_source_file(judgment, file_is_anonymised=True)

        url = reverse("check_duplicate_file") + "?sha256=" + judgment.source_file.sha256

        response = self.app.get(url)
        self.assertEqual(200, response.status_code)
        self.assertIn(
            judgment.title,
            response.text,
        )

        # log out
        self.app.reset()
        response = self.app.get(url, user=None, status=403)
        self.assertEqual(403, response.status_code)


class TestDocumentAdminHtmlEdit(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.app.set_user(User.objects.get(username="admin@example.com"))
        self.document = GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2022, 9, 14),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title="Admin source_html integration",
        )
        doc_content = self.document.get_or_create_document_content()
        doc_content.set_source_html("<h1>Initial</h1><p>Initial</p>")
        self.document.save()

    def test_admin_edit_source_html_updates_content_text_and_toc(self):
        change_url = reverse(
            "admin:peachjam_genericdocument_change",
            kwargs={"object_id": self.document.pk},
        )
        form = self.app.get(change_url).forms["genericdocument_form"]
        form["source_html"] = "<h1>Edited Heading</h1><p>Edited body</p>"

        response = form.submit()
        self.assertEqual(302, response.status_code)

        self.document.refresh_from_db()
        self.assertEqual(
            "<h1>Edited Heading</h1><p>Edited body</p>",
            self.document.document_content.source_html,
        )
        self.assertIn("Edited body", self.document.document_content.content_html)
        self.assertIn("Edited Heading", self.document.document_content.content_text)
        self.assertTrue(self.document.document_content.toc_json)


class TestJournalArticleAdmin(WebTest):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.app.set_user(User.objects.get(username="admin@example.com"))
        self.journal = Journal.objects.create(
            title="Contemporary Labour Law",
            slug="contemporary-labour-law",
        )
        self.volume = VolumeIssue.objects.create(
            title="Volume 1",
            journal=self.journal,
        )

    def test_add_journal_article_with_journal_and_volume(self):
        journal_article_add_url = reverse("admin:peachjam_journalarticle_add")
        journal_article_list_url = reverse("admin:peachjam_journalarticle_changelist")

        form = self.app.get(journal_article_add_url).forms["journalarticle_form"]
        form["title"] = "New journal article"
        form["jurisdiction"] = "ZA"
        form["language"] = "en"
        form["journal"].force_value(str(self.journal.pk))
        form["volume"].force_value(str(self.volume.pk))
        form["date_0"] = "19"
        form["date_1"] = "3"
        form["date_2"] = "2026"
        form["frbr_uri_doctype"] = "doc"
        form["frbr_uri_number"] = "new-journal-article"

        response = form.submit()
        self.assertRedirects(response, journal_article_list_url)

        article = JournalArticle.objects.get(title="New journal article")
        self.assertEqual(self.journal.pk, article.journal_id)
        self.assertEqual(self.volume.pk, article.volume_id)
        self.assertTrue(hasattr(article, "document_content"))
