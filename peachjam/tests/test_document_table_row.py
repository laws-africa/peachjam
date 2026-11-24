from datetime import date
from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils.formats import date_format


class DocumentTableRowTestCase(SimpleTestCase):
    def render_row(self, **kwargs):
        document = SimpleNamespace(
            pk=1,
            title="A document",
            get_absolute_url="/doc/",
            labels=SimpleNamespace(all=[]),
            work=SimpleNamespace(languages=["eng"]),
            children=None,
            is_group=False,
            listing_taxonomies=None,
            **kwargs,
        )
        return render_to_string(
            "peachjam/_document_table_row.html", {"document": document}
        )

    def test_flynote_shown_for_other_doc_types(self):
        html = self.render_row(doc_type="judgment_stub", flynote="A stub flynote")
        self.assertIn("A stub flynote", html)

    def test_no_flynote_for_other_doc_types(self):
        html = self.render_row(doc_type="legislation", flynote="")
        self.assertNotIn("fst-italic", html)

    def test_group_heading_has_an_empty_date_cell(self):
        document = SimpleNamespace(is_group=True, title="A")
        html = render_to_string(
            "peachjam/_document_table_row.html",
            {"document": document, "doc_table_show_date": True},
        )
        self.assertEqual(
            BeautifulSoup(html, "html.parser")
            .select_one(".cell-date")
            .get_text(strip=True),
            "",
        )

    def test_row_date_uses_override_or_document_date(self):
        expression_date = date(2026, 1, 1)
        publication_date = date(2026, 2, 1)
        document = SimpleNamespace(
            pk=1,
            title="A document",
            get_absolute_url="/doc/",
            is_group=False,
            date=expression_date,
            doc_type="legislation",
            flynote="",
        )
        for override, expected in [
            (None, expression_date),
            (publication_date, publication_date),
        ]:
            with self.subTest(override=override):
                html = render_to_string(
                    "peachjam/_document_table_row.html",
                    {
                        "document": document,
                        "doc_table_show_date": True,
                        "document_date": override,
                    },
                )
                self.assertEqual(
                    BeautifulSoup(html, "html.parser")
                    .select_one(".cell-date")
                    .get_text(strip=True),
                    date_format(expected, "DATE_FORMAT"),
                )
