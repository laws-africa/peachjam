from django.test import TestCase


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents", "tests/languages"]
    maxDiff = None

    def test_years_filter_with_single_year(self):
        response = self.client.get("/legislation/?years=2007")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["facet_data"]["years"]["options"],
            [("2005", "2005"), ("1979", "1979"), ("1969", "1969")],
        )

    def test_alphabet_filter(self):
        response = self.client.get("/legislation/?alphabet=a")

        self.assertEqual(response.status_code, 200)

        documents = response.context.get("documents")
        for title in [doc.title for doc in documents]:
            self.assertTrue(title.startswith("A"))
