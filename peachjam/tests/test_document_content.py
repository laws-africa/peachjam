from datetime import date
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from peachjam.models import Country, GenericDocument, Language


class DocumentContentHooksTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def make_doc(self, title, is_akn=False):
        doc = GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2022, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title=title,
            content_html_is_akn=is_akn,
        )
        return doc

    def test_source_change_derives_content_html_and_text(self):
        doc = self.make_doc("Hook source derives content")
        doc_content = doc.get_or_create_document_content()
        doc_content.source_html = "<p>Initial</p>"
        doc_content.save()

        doc_content.source_html = "<h1>Heading</h1><p>Body</p>"
        doc_content.save()
        doc_content.refresh_from_db()
        doc.refresh_from_db()

        self.assertIn("Heading", doc_content.content_html)
        self.assertIn("Body", doc_content.content_html)
        self.assertIsNotNone(doc_content.content_text)
        self.assertIn("Heading", doc_content.content_text)
        self.assertIn("Body", doc_content.content_text)

    def test_source_change_does_not_overwrite_akn_content_html(self):
        doc = self.make_doc("Hook AKN bypass", is_akn=True)
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<div><p>Original AKN HTML</p></div>"
        doc_content.source_html = "<p>Source 1</p>"
        doc_content.save()

        doc_content.source_html = "<p>Source 2</p>"
        doc_content.save()
        doc_content.refresh_from_db()

        self.assertEqual(
            "<div><p>Original AKN HTML</p></div>", doc_content.content_html
        )


class ContentHtmlIsAknMigrationTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def make_doc(self, title, is_akn=False):
        return GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2022, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title=title,
            content_html_is_akn=is_akn,
        )

    def test_migration_backfills_documentcontent_content_html_is_akn(self):
        migration = import_module(
            "peachjam.migrations.0277_migrate_content_html_is_akn_to_documentcontent"
        )

        true_doc = self.make_doc("Migration True", is_akn=True)
        false_doc = self.make_doc("Migration False", is_akn=False)

        # existing false value should remain false
        false_content = false_doc.get_or_create_document_content()
        false_content.content_html_is_akn = False
        false_content.save()

        migration.migrate_content_html_is_akn(apps, None)

        true_doc.refresh_from_db()
        false_doc.refresh_from_db()
        self.assertTrue(true_doc.document_content.content_html_is_akn)
        self.assertFalse(false_doc.document_content.content_html_is_akn)
