from datetime import date
from urllib.parse import parse_qs, quote, urlparse

from django.test import TestCase
from django.urls import reverse

from peachjam.models import Country, GenericDocument, Language


class ComparePortionsViewTest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def make_akn_document(self, title, number, doctype="act"):
        document = GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2020, 1, 2),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype=doctype,
            frbr_uri_number=number,
            title=title,
            published=True,
        )
        content = document.get_or_create_document_content(True)
        content.content_html_is_akn = True
        content.content_html = f"""
          <div class="akn-akomaNtoso">
            <section id="chp_1" data-eid="chp_1">
              <span class="akn-num">Chapter 1</span>
              <p>{title} chapter content</p>
              <section id="chp_1__sec_1" data-eid="chp_1__sec_1">
                <span class="akn-num">1.</span>
                <p>{title} section content</p>
              </section>
            </section>
          </div>
        """
        content.toc_json = [
            {
                "id": "chp_1",
                "title": "Chapter 1",
                "children": [
                    {
                        "id": "chp_1__sec_1",
                        "title": "Section 1",
                        "children": [],
                    }
                ],
            }
        ]
        content.save()
        return document

    def provision_uri(self, document, portion_id="chp_1"):
        return f"{document.expression_frbr_uri}/~{portion_id}"

    def test_blank_compare_renders_two_choosers(self):
        response = self.client.get(reverse("compare_portions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compare provisions side-by-side")
        self.assertContains(response, 'id="compare-chooser-a"')
        self.assertContains(response, 'id="compare-chooser-b"')

    def test_one_selected_side_renders_provision_and_other_chooser(self):
        doc = self.make_akn_document("First Act", "1")

        response = self.client.get(
            reverse("compare_portions"), {"uri-a": self.provision_uri(doc)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First Act chapter content")
        self.assertContains(response, 'id="compare-chooser-b"')

    def test_two_selected_sides_render_both_provisions(self):
        doc_a = self.make_akn_document("First Act", "1")
        doc_b = self.make_akn_document("Second Act", "2")

        response = self.client.get(
            reverse("compare_portions"),
            {
                "uri-a": self.provision_uri(doc_a, "chp_1__sec_1"),
                "uri-b": self.provision_uri(doc_b, "chp_1"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First Act section content")
        self.assertContains(response, "Second Act chapter content")

    def test_only_uri_b_redirects_to_uri_a(self):
        doc = self.make_akn_document("First Act", "1")
        uri = self.provision_uri(doc)

        response = self.client.get(reverse("compare_portions"), {"uri-b": uri})

        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual([uri], query["uri-a"])
        self.assertNotIn("uri-b", query)

    def test_old_params_redirect_to_canonical_provision_uris(self):
        doc_a = self.make_akn_document("First Act", "1")
        doc_b = self.make_akn_document("Second Act", "2")

        response = self.client.get(
            reverse("compare_portions"),
            {
                "uri-a": doc_a.expression_frbr_uri,
                "portion-a": "chp_1",
                "uri-b": doc_b.expression_frbr_uri,
                "portion-b": "chp_1__sec_1",
            },
        )

        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response["Location"]).query)
        self.assertEqual([self.provision_uri(doc_a)], query["uri-a"])
        self.assertEqual([self.provision_uri(doc_b, "chp_1__sec_1")], query["uri-b"])

    def test_invalid_selected_provision_404s(self):
        doc = self.make_akn_document("First Act", "1")

        response = self.client.get(
            reverse("compare_portions"), {"uri-a": self.provision_uri(doc, "missing")}
        )

        self.assertEqual(response.status_code, 404)

    def test_chooser_search_returns_only_eligible_documents(self):
        self.make_akn_document("First Act", "1")
        self.make_akn_document("Second Act", "2")
        GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=date(2020, 1, 2),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="act",
            frbr_uri_number="3",
            title="Second ineligible Act",
            published=True,
        )

        response = self.client.get(
            reverse("compare_chooser"),
            {"side": "a", "search": "1", "q": "Second"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Act")
        self.assertNotContains(response, 'id="compare-column-a"')
        self.assertNotContains(response, 'id="compare-document-search-a"')
        self.assertContains(response, 'hx-swap="outerHTML"')
        self.assertNotContains(response, "Second ineligible Act")

    def test_chooser_search_filters_to_selected_side_doctype(self):
        selected = self.make_akn_document("First Act", "1")
        self.make_akn_document("Second Act", "2")
        self.make_akn_document("Second Generic Document", "second-doc", doctype="doc")

        response = self.client.get(
            reverse("compare_chooser"),
            {
                "side": "a",
                "search": "1",
                "q": "Second",
                "uri-a": self.provision_uri(selected),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Act")
        self.assertNotContains(response, "Second Generic Document")

    def test_blank_side_search_filters_to_opposite_side_doctype(self):
        selected = self.make_akn_document("First Act", "1")
        self.make_akn_document("Second Act", "2")
        self.make_akn_document("Second Generic Document", "second-doc", doctype="doc")

        response = self.client.get(
            reverse("compare_chooser"),
            {
                "side": "b",
                "search": "1",
                "q": "Second",
                "uri-a": self.provision_uri(selected),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Act")
        self.assertNotContains(response, "Second Generic Document")

    def test_chooser_document_uri_renders_toc_links(self):
        doc = self.make_akn_document("First Act", "1")

        response = self.client.get(
            reverse("compare_chooser"),
            {"side": "b", "document-uri": doc.expression_frbr_uri},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="compare-column-b"')
        self.assertContains(response, "la-table-of-contents-controller")
        self.assertContains(response, "Search table of contents")
        self.assertContains(response, "&quot;href&quot;")
        self.assertContains(response, "Chapter 1")
        self.assertContains(response, quote(self.provision_uri(doc), safe=""))
        self.assertContains(
            response, quote(self.provision_uri(doc, "chp_1__sec_1"), safe="")
        )

    def test_chooser_for_selected_side_includes_cancel(self):
        doc = self.make_akn_document("First Act", "1")

        response = self.client.get(
            reverse("compare_chooser"),
            {"side": "a", "uri-a": self.provision_uri(doc)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="compare-column-a"')
        self.assertContains(response, "First Act")
        self.assertContains(response, "Cancel")
        self.assertContains(response, "cancel=1")

    def test_cancel_chooser_restores_selected_provision(self):
        doc = self.make_akn_document("First Act", "1")

        response = self.client.get(
            reverse("compare_chooser"),
            {
                "side": "a",
                "cancel": "1",
                "uri-a": self.provision_uri(doc),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="compare-column-a"')
        self.assertContains(response, "First Act chapter content")
        self.assertNotContains(response, 'id="compare-chooser-a"')
