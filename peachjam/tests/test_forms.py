from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from peachjam.forms import BaseDocumentFilterForm


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/languages"]
    maxDiff = None

    def test_years_filter_with_single_year(self):
        response = self.client.get(reverse("legislation_list") + "?years=2007")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["facet_data"]["years"]["options"],
            [("2005", "2005"), ("1979", "1979"), ("1969", "1969")],
        )

    def test_alphabet_filter(self):
        response = self.client.get(reverse("legislation_list") + "?alphabet=a")

        self.assertEqual(response.status_code, 200)

        documents = response.context.get("documents")
        for title in [doc.title for doc in documents]:
            self.assertTrue(title.startswith("A"))

    def test_document_table_form_renders_accessibility_hooks_for_long_facets(self):
        request = RequestFactory().get("/documents/")
        form = BaseDocumentFilterForm({}, {})
        html = render_to_string(
            "peachjam/_document_table_form.html",
            {
                "request": request,
                "doc_table_form_id": "doc-table-form-test",
                "doc_table_id": "doc-table-test",
                "doc_table_offcanvas_id": "doc-table-filters-offcanvas-test",
                "doc_table_offcanvas_title_id": "doc-table-filters-offcanvas-test-title",
                "doc_table_filter_input_id": "doc-table-form-test-filter-input",
                "taxonomy_tree": [],
                "is_leaf_node": False,
                "show_clear_all": False,
                "facet_data": {
                    "judges": {
                        "label": "Judges",
                        "options": [(f"judge-{i}", f"Judge {i}") for i in range(9)],
                        "values": [],
                        "type": "checkbox",
                    },
                    "years": {
                        "label": "Years",
                        "options": [("2024", "2024")],
                        "values": [],
                        "type": "checkbox",
                    },
                },
                "form": form,
                "documents": [],
                "doc_count": 0,
                "doc_count_noun": "document",
                "doc_count_noun_plural": "documents",
                "doc_table_show_counts": True,
                "hide_pagination": True,
                "paginator": None,
            },
            request=request,
        )

        self.assertIn('href="#doc-table-test-results-heading"', html)
        self.assertIn('id="doc-table-form-test-group-judges"', html)
        self.assertIn('aria-labelledby="doc-table-form-test-group-heading-0"', html)
        self.assertEqual(html.count("data-close-offcanvas"), 3)
        self.assertIn('href="#doc-table-form-test-group-heading-1"', html)
        self.assertIn("data-document-table-results-target", html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("No documents found.", html)

    def test_long_sidebar_lists_render_bypass_navigation(self):
        request = RequestFactory().get("/judgments/ecowascj/")
        registries = [
            SimpleNamespace(
                code=f"registry-{i}",
                name=f"Registry {i}",
                get_absolute_url=f"/registry/{i}/",
            )
            for i in range(9)
        ]
        years = [
            SimpleNamespace(year=2000 + i, url=f"/years/{2000 + i}/") for i in range(9)
        ]

        registries_html = render_to_string(
            "peachjam/_registries.html",
            {
                "request": request,
                "registries": registries,
                "registry_groups": [registries[:5], registries[5:]],
                "registry": SimpleNamespace(code=""),
                "registry_label_plural": "Registries",
            },
            request=request,
        )
        years_html = render_to_string(
            "peachjam/_years_list.html",
            {
                "request": request,
                "years": years,
                "year": None,
                "all_years_url": "/years/",
            },
            request=request,
        )

        self.assertIn("Skip past Registries", registries_html)
        self.assertIn(
            'aria-labelledby="registries-heading-judgmentsecowascj"', registries_html
        )
        self.assertIn('id="registries-end-judgmentsecowascj"', registries_html)
        self.assertIn("Skip past years", years_html)
        self.assertIn('aria-labelledby="years-heading-judgmentsecowascj"', years_html)
        self.assertIn('id="years-end-judgmentsecowascj"', years_html)
