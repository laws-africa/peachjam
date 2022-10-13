from django.test import TestCase


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["documents/sample_documents", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_years_filter(self):
        response = self.client.get("/legal_instruments/?years=2007")
        breakpoint()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["facet_data"]["years"], [2007])
