import os
from datetime import date

from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django_webtest import WebTest
from webtest import Upload

from peachjam.admin import JournalArticleAdmin
from peachjam.models import (
    Country,
    GenericDocument,
    Journal,
    JournalArticle,
    Judgment,
    Language,
    VolumeIssue,
)


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


class TestJournalArticleAdmin(TestCase):
    fixtures = ["tests/users", "tests/countries", "tests/languages"]

    def setUp(self):
        self.user = User.objects.get(username="admin@example.com")
        self.factory = RequestFactory()
        self.journal = Journal.objects.create(
            title="Contemporary Labour Law",
            slug="contemporary-labour-law",
        )
        self.volume = VolumeIssue.objects.create(
            title="Volume 1",
            journal=self.journal,
        )

    def test_add_journal_article_with_journal_and_volume(self):
        request = self.factory.get(reverse("admin:peachjam_journalarticle_add"))
        request.user = self.user
        model_admin = JournalArticleAdmin(JournalArticle, admin.site)
        form_class = model_admin.get_form(
            request,
            obj=None,
            fields=flatten_fieldsets(model_admin.get_fieldsets(request, obj=None)),
        )
        form = form_class(
            data={
                "title": "New journal article",
                "jurisdiction": "ZA",
                "language": "en",
                "journal": str(self.journal.pk),
                "volume": str(self.volume.pk),
                "date_0": "19",
                "date_1": "3",
                "date_2": "2026",
                "frbr_uri_doctype": "doc",
                "frbr_uri_subtype": "",
                "frbr_uri_actor": "",
                "frbr_uri_date": "2026-03-19",
                "frbr_uri_number": "new-journal-article",
                "published": "",
                "citation": "",
                "source_url": "",
                "source_html": "",
                "allow_robots": "on",
                "restricted": "",
                "edit_activity_stage": "initial",
                "edit_activity_start": "2026-03-19 00:00:00",
                "publication_file-TOTAL_FORMS": "0",
                "publication_file-INITIAL_FORMS": "0",
                "publication_file-MIN_NUM_FORMS": "0",
                "publication_file-MAX_NUM_FORMS": "1000",
                "alternative_names-TOTAL_FORMS": "0",
                "alternative_names-INITIAL_FORMS": "0",
                "alternative_names-MIN_NUM_FORMS": "0",
                "alternative_names-MAX_NUM_FORMS": "1000",
                "attachedfiles_set-TOTAL_FORMS": "0",
                "attachedfiles_set-INITIAL_FORMS": "0",
                "attachedfiles_set-MIN_NUM_FORMS": "0",
                "attachedfiles_set-MAX_NUM_FORMS": "1000",
                "images-TOTAL_FORMS": "0",
                "images-INITIAL_FORMS": "0",
                "images-MIN_NUM_FORMS": "0",
                "images-MAX_NUM_FORMS": "1000",
                "custom_properties-TOTAL_FORMS": "0",
                "custom_properties-INITIAL_FORMS": "0",
                "custom_properties-MIN_NUM_FORMS": "0",
                "custom_properties-MAX_NUM_FORMS": "1000",
                "background_task-task-creator_content_type-creator_object_id-TOTAL_FORMS": "0",
                "background_task-task-creator_content_type-creator_object_id-INITIAL_FORMS": "0",
                "background_task-task-creator_content_type-creator_object_id-MIN_NUM_FORMS": "0",
                "background_task-task-creator_content_type-creator_object_id-MAX_NUM_FORMS": "1000",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        self.assertEqual(self.journal.pk, article.journal_id)
        self.assertEqual(self.volume.pk, article.volume_id)
        self.assertTrue(hasattr(article, "document_content"))
