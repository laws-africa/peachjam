from datetime import date

from django.test import TestCase

from peachjam.models import Country, DocumentContent, JournalArticle, Language


class DocumentChatToolsTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_get_document_text_creates_missing_document_content_for_journal_article(
        self,
    ):
        article = JournalArticle.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2024, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            frbr_uri_number="chat-regression",
            title="Chat regression",
            publisher="Publisher",
        )

        self.assertFalse(DocumentContent.objects.filter(document=article).exists())

        text = article.get_content_as_text()

        self.assertEqual("", text)
        self.assertTrue(DocumentContent.objects.filter(document=article).exists())
