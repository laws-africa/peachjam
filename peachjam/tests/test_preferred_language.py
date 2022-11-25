from django.test import TestCase


class TestPreferredLanguage(TestCase):
    fixtures = ["documents/sample_documents", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_preferred_language(self):
        response = self.client.get("/legal_instruments/")

        assert response.context.get("documents").count() == 2
