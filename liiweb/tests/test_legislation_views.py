from django.test import TestCase


class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_legislation_listing_national_only(self):
        response = self.client.get("/legislation/all")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            ["D", "Divorce Act, 1979"],
            [doc.title for doc in response.context.get("documents")],
        )
