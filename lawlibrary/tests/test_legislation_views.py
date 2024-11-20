from django.test import TestCase


class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def test_legislation_listing_locality_redirect(self):
        response = self.client.get("/legislation/au/all")
        self.assertEqual(response.status_code, 302)

    def test_legislation_listing_locality(self):
        response = self.client.get("/legislation/aa-au/all")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            [
                "A",
                "African Civil Aviation Commission Constitution (AFCAC)",
                "African Union Non-Aggression and Common Defence Pact",
            ],
            [doc.title for doc in response.context.get("documents")],
        )
