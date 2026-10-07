from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


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
