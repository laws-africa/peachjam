from datetime import date

from cobalt.uri import FrbrUri
from django.test import TestCase

from peachjam.models import (
    Book,
    CoreDocument,
    Country,
    Gazette,
    GenericDocument,
    JournalArticle,
    Language,
    get_country_and_locality,
)


class CoreDocumentTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def test_document_text_from_html(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/aa-au/doc/activity-report/2017/nn/eng@2017-07-03"
        )
        self.assertFalse(hasattr(doc, "document_content"))
        self.assertEqual(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            doc.get_content_as_text().strip()[:69],
        )
        self.assertTrue(hasattr(doc, "document_content"))
        self.assertEqual(
            "Activity Report of the Pan-African Parliament, July 2016 to June 2017",
            doc.document_content.content_text.strip()[:69],
        )

        # change the source and update
        doc.content_html = "<p>test</p>"
        doc._content_html_tree = None
        doc.update_text_content()
        self.assertEqual("test", doc.get_content_as_text())

        doc.refresh_from_db()
        self.assertEqual("test", doc.get_content_as_text())

    def test_get_cited_work_frbr_uris(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2020-10-22"
        )

        frbr_uris = sorted(list(doc.get_cited_work_frbr_uris()))
        self.assertEqual(
            [
                "/akn/za/act/1927/38",
                "/akn/za/act/1935/32",
                "/akn/za/act/1939/22",
                "/akn/za/act/1943/17",
                "/akn/za/act/1944/32",
                "/akn/za/act/1945/35",
                "/akn/za/act/1953/37",
                "/akn/za/act/1956/24",
                "/akn/za/act/1960/33",
                "/akn/za/act/1965/66",
                "/akn/za/act/1966/13",
                "/akn/za/act/1968/70",
                "/akn/za/act/1970/54",
                "/akn/za/act/1973/18",
                "/akn/za/act/1975/55",
                "/akn/za/act/1996/65",
                "/akn/za/act/1996/constitution",
                "/akn/za/act/ord/1955/25",
                "/akn/za/act/ord/1961/31",
            ],
            frbr_uris,
        )

    def test_get_cited_work_frbr_uris_html(self):
        doc = CoreDocument.objects.get(
            expression_frbr_uri="/akn/za/act/1979/70/eng@2020-10-22"
        )
        doc.content_html = """<div>
<p><a class="sdfootnotesym" href="#sdfootnote5anc" name="sdfootnote5sym">5</a> <em>Motata v Minister of Justice and
Constitutional Development and Others </em><a href="/akn/za/judgment/zagpphc/2012/196" aria-expanded="false">[2012]
ZAGPPHC 196</a> para 6.</p>
</div>
<div>
<p><a class="sdfootnotesym" href="#sdfootnote6anc" name="sdfootnote6sym">6</a> <em>Motata v Minister of Justice and
Constitutional Development and Another </em><a href="/akn/za/judgment/zagpphc/2016/1063" aria-expanded="false">[2016]
ZAGPPHC 1063</a>.</p>
</div>"""
        doc.content_html_is_akn = False

        frbr_uris = sorted(list(doc.get_cited_work_frbr_uris()))
        self.assertEqual(
            ["/akn/za/judgment/zagpphc/2012/196", "/akn/za/judgment/zagpphc/2016/1063"],
            frbr_uris,
        )

    def test_book(self):
        book = Book(
            jurisdiction=Country.objects.get(pk="ZM"),
            date=date(2020, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_number="test",
            title="test",
        )
        book.save()
        self.assertEqual("doc", book.frbr_uri_doctype)
        self.assertEqual("book", book.frbr_uri_subtype)

    def test_journal(self):
        journal = JournalArticle(
            jurisdiction=Country.objects.get(pk="ZM"),
            date=date(2020, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_number="test",
            title="test",
        )
        journal.save()
        self.assertEqual("doc", journal.frbr_uri_doctype)
        self.assertEqual("journal-article", journal.frbr_uri_subtype)

    def test_clean_content_html(self):
        doc = CoreDocument()
        self.assertIsNone(doc.clean_content_html(""""""))
        self.assertIsNone(doc.clean_content_html("""<aoeu"""))
        self.assertIsNone(doc.clean_content_html("""<div>   \n&nbsp;  \n</div>"""))
        self.assertEqual(
            doc.clean_content_html("""<div>test</div>"""), """<div>test</div>"""
        )

    def test_gazette(self):
        frbr_uri = FrbrUri.parse(
            "/akn/za/officialGazette/provincial-gazette/2024-09-13/3585/eng@2024-09-13"
        )
        country, locality = get_country_and_locality("za")

        gazette = Gazette.objects.create(
            **{
                "expression_frbr_uri": frbr_uri.expression_uri(),
                "jurisdiction": country,
                "locality": locality,
                "frbr_uri_doctype": frbr_uri.doctype,
                "frbr_uri_subtype": frbr_uri.subtype,
                "frbr_uri_actor": frbr_uri.actor,
                "frbr_uri_number": frbr_uri.number,
                "frbr_uri_date": frbr_uri.date,
                "language": Language.objects.get(pk="en"),
                "date": date.fromisoformat("2024-09-13"),
                "title": "gazette title",
                "publication": "Provincial Gazette",
                "key": "key",
            }
        )
        self.assertEqual(frbr_uri.expression_uri(), gazette.expression_frbr_uri)

    def test_generic_document(self):
        doc = GenericDocument(
            jurisdiction=Country.objects.get(pk="ZM"),
            date=date(2020, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title="My Test",
        )
        doc.save()
        self.assertEqual("my-test", doc.frbr_uri_number)
