from countries_plus.models import Country
from django.test import TestCase

from peachjam.models import Locality


class LegislationViewsTest(TestCase):
    fixtures = ["tests/countries", "documents/sample_documents"]

    def setUp(self):
        za = Country.objects.get(pk="ZA")
        Locality.objects.get_or_create(
            code="gp", jurisdiction=za, defaults={"name": "Gauteng"}
        )
        Locality.objects.get_or_create(
            code="cpt", jurisdiction=za, defaults={"name": "Cape Town"}
        )

    def test_legislation_locality(self):
        response = self.client.get("/legislation/localities")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/legislation/provincial")

        response = self.client.get("/legislation/provincial")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/legislation/municipal")
        self.assertEqual(response.status_code, 200)

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
