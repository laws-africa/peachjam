from datetime import date

from django.test import TestCase

from peachjam.models import Country, DocumentContent, GenericDocument, Language


def _make_doc(title, is_akn=False):
    doc = GenericDocument.objects.create(
        jurisdiction=Country.objects.get(pk="ZA"),
        date=date(2022, 1, 1),
        language=Language.objects.get(pk="en"),
        frbr_uri_doctype="doc",
        title=title,
    )
    doc_content = doc.get_or_create_document_content()
    doc_content.content_html_is_akn = is_akn
    doc_content.save()
    return doc


class DocumentContentTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_source_change_derives_content_html_and_text(self):
        doc = _make_doc("Hook source derives content")
        doc_content = doc.get_or_create_document_content(True)
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

    def test_source_change_updates_akn_content_html(self):
        doc = _make_doc("Hook AKN source update", is_akn=True)
        doc_content = doc.get_or_create_document_content(True)
        doc_content.source_html = "<p>Source 1</p>"
        doc_content.save()

        doc_content.source_html = "<p>Source 2</p>"
        doc_content.save()
        doc_content.refresh_from_db()

        self.assertEqual("<p>Source 2</p>", doc_content.content_html)

    def test_get_or_create_uses_documentcontent_content_html_is_akn(self):
        true_doc = _make_doc("Migration True", is_akn=True)
        false_doc = _make_doc("Migration False", is_akn=False)

        # existing false value should remain false
        false_content = false_doc.get_or_create_document_content(True)
        false_content.content_html_is_akn = False
        false_content.save()

        true_doc.refresh_from_db()
        false_doc.refresh_from_db()
        true_doc.get_or_create_document_content()
        false_doc.get_or_create_document_content()
        self.assertTrue(true_doc.document_content.content_html_is_akn)
        self.assertFalse(false_doc.document_content.content_html_is_akn)

    def test_clean_content_html(self):
        content = DocumentContent()
        self.assertIsNone(content.clean_content_html(""""""))
        self.assertIsNone(content.clean_content_html("""<aoeu"""))
        self.assertIsNone(content.clean_content_html("""<div>   \n&nbsp;  \n</div>"""))
        self.assertEqual(
            content.clean_content_html("""<div>test</div>"""), """<div>test</div>"""
        )


class GetOrCreateDocumentContentTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_caching_returns_same_object(self):
        """get_or_create_document_content() returns the same Python object on repeated calls."""
        doc = _make_doc("Cache test")
        first = doc.get_or_create_document_content()
        second = doc.get_or_create_document_content()
        self.assertIs(first, second)

    def test_unsaved_document_returns_in_memory_content(self):
        """For an unsaved document, get_or_create_document_content() returns an in-memory
        DocumentContent without hitting the DB."""
        doc = GenericDocument(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2022, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title="Unsaved doc",
        )
        doc_content = doc.get_or_create_document_content()
        self.assertIsNotNone(doc_content)
        self.assertIsNone(doc_content.pk)
        self.assertEqual(0, DocumentContent.objects.count())

    def test_multiple_saves_dont_duplicate_document_content(self):
        """Saving a document multiple times must not create extra DocumentContent rows."""
        doc = _make_doc("Multi-save test")
        count_before = DocumentContent.objects.count()
        doc.save()
        doc.save()
        self.assertEqual(count_before, DocumentContent.objects.count())

    def test_get_or_create_after_refresh_from_db_returns_consistent_pk(self):
        """After refresh_from_db(), get_or_create_document_content() returns a DocumentContent
        with the same pk as before (cache may survive refresh, but pk is stable)."""
        doc = _make_doc("Cache refresh test")
        first = doc.get_or_create_document_content()
        doc.refresh_from_db()
        second = doc.get_or_create_document_content()
        self.assertEqual(first.pk, second.pk)


class SetContentHtmlTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_set_content_html_persisted_after_doc_save(self):
        """Content set via DocumentContent.set_content_html() is written to DB when the document is saved."""
        doc = _make_doc("Persist set_content_html")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.set_content_html("<p>Persisted</p>")
        doc_content.save()
        self.assertIn("Persisted", doc_content.content_html)

    def test_set_content_html_cleans_empty_html(self):
        """DocumentContent.set_content_html() with effectively-empty HTML leaves content_html as None."""
        doc = _make_doc("Empty HTML cleanup")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.set_content_html("<div>   \n&nbsp;  \n</div>")
        doc_content.save()
        self.assertIsNone(doc_content.content_html)

    def test_set_content_html_akn_skips_cleaning(self):
        """For AKN documents, DocumentContent.set_content_html() stores the raw HTML without cleaning."""
        doc = _make_doc("AKN skip clean", is_akn=True)
        raw_akn = "<div class='akn-akomaNtoso'><p>AKN content</p></div>"
        doc_content = doc.get_or_create_document_content(True)
        doc_content.set_content_html(raw_akn)
        doc_content.save()
        self.assertEqual(raw_akn, doc_content.content_html)

    def test_sets_source_html_and_derives_content(self):
        """Setting source_html on DocumentContent stores source_html and derives content_html."""
        doc = _make_doc("Source-derived content")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.set_source_html("<p>Source text</p>")
        doc_content.save()
        self.assertEqual("<p>Source text</p>", doc_content.source_html)
        self.assertIn("Source text", doc_content.content_html)

    def test_generates_toc_from_headings(self):
        """Setting source_html on DocumentContent with heading tags generates a non-empty TOC."""
        doc = _make_doc("TOC generation")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.set_source_html("<h1>Chapter 1</h1><p>Introduction</p>")
        doc_content.save()
        self.assertIsNotNone(doc_content.toc_json)
        self.assertTrue(len(doc_content.toc_json) > 0)


class DocumentContentHtmlTreeTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_content_html_tree_is_cached(self):
        """content_html_tree returns the same object on repeated access."""
        doc = _make_doc("Tree cache")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<p>Hello</p>"
        tree1 = doc_content.content_html_tree
        tree2 = doc_content.content_html_tree
        self.assertIs(tree1, tree2)

    def test_content_html_tree_cleared_by_set_content_html(self):
        """set_content_html() invalidates the cached HTML tree."""
        doc = _make_doc("Tree invalidation")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<p>First</p>"
        _ = doc_content.content_html_tree  # warm the cache
        doc_content.set_content_html("<p>Second</p>")
        self.assertIsNone(doc_content._content_html_tree)

    def test_content_html_tree_reflects_updated_content(self):
        """After setting new content_html, content_html_tree reflects the new content."""
        doc = _make_doc("Tree update")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<p>Before</p>"
        _ = doc_content.content_html_tree
        doc_content.set_content_html("<p>After</p>")
        self.assertIn("After", doc_content.content_html_tree.text_content())


class DocumentContentDerivedFieldsTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_toc_generated_on_content_html_save(self):
        """The BEFORE_SAVE hook generates a TOC when content_html changes."""
        doc = _make_doc("TOC hook")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.content_html = "<h1>Section</h1><p>Text</p>"
        doc_content.save()
        doc_content.refresh_from_db()
        self.assertIsNotNone(doc_content.toc_json)
        self.assertTrue(len(doc_content.toc_json) > 0)

    def test_content_text_updated_on_content_html_save(self):
        """The BEFORE_SAVE hook extracts plain text when content_html changes."""
        doc = _make_doc("Text hook")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.content_html = "<p>Extracted text</p>"
        doc_content.save()
        self.assertIsNotNone(doc_content.content_text)
        self.assertIn("Extracted text", doc_content.content_text)

    def test_toc_not_generated_for_akn(self):
        """update_toc_json_from_content_html() is a no-op for AKN documents."""
        doc = _make_doc("AKN no TOC", is_akn=True)
        doc_content = doc.get_or_create_document_content()
        doc_content.toc_json = [{"id": "existing"}]
        doc_content.content_html = "<h1>Chapter</h1>"
        doc_content.update_toc_json_from_content_html()
        self.assertEqual([{"id": "existing"}], doc_content.toc_json)

    def test_empty_content_html_produces_empty_toc(self):
        """If content_html is None, update_toc_json_from_content_html() sets toc_json=[]."""
        doc = _make_doc("Empty toc")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = None
        doc_content.update_toc_json_from_content_html()
        self.assertEqual([], doc_content.toc_json)

    def test_update_content_text_from_html(self):
        """update_content_text_from_html() extracts all text from content_html."""
        doc = _make_doc("Text extraction")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<div><p>First</p><p>Second</p></div>"
        doc_content.update_content_text_from_html()
        self.assertIn("First", doc_content.content_text)
        self.assertIn("Second", doc_content.content_text)

    def test_update_content_text_from_html_with_no_content(self):
        """update_content_text_from_html() sets empty string when content_html is None."""
        doc = _make_doc("No content text")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = None
        doc_content.update_content_text_from_html()
        self.assertEqual("", doc_content.content_text)

    def test_source_html_derives_content_html(self):
        """apply_source_to_content() copies source_html into content_html (with cleaning)."""
        doc = _make_doc("Apply source to content")
        doc_content = doc.get_or_create_document_content(True)
        doc_content.source_html = "<p>Source paragraph</p>"
        doc_content.save()
        self.assertIn("Source paragraph", doc_content.content_html)


class GetContentAsTextTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_get_content_as_text_returns_existing_content_text(self):
        """get_content_as_text() returns content_text when already populated."""
        doc = _make_doc("Existing text")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_text = "Pre-extracted text"
        doc_content.save()
        self.assertEqual("Pre-extracted text", doc_content.get_content_as_text())

    def test_get_content_as_text_triggers_extraction_when_none(self):
        """get_content_as_text() triggers update_text_content() when content_text is None."""
        doc = _make_doc("Trigger extraction")
        doc_content = doc.get_or_create_document_content()
        doc_content.content_html = "<p>Auto-extracted</p>"
        doc_content.content_text = None
        doc_content.save()
        result = doc_content.get_content_as_text()
        self.assertIsNotNone(result)
        self.assertIn("Auto-extracted", result)
