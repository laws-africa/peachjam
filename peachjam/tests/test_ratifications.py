import datetime

from countries_plus.models import Country
from django.test import TestCase

from peachjam.adapters import RatificationsAdapter
from peachjam.models import Ratification, RatificationCountry, Work


class TestRatificationsAdapter(TestCase):
    fixtures = ["tests/countries", "tests/languages", "documents/sample_documents"]

    def setUp(self):
        self.adapter = RatificationsAdapter(
            None, {"api_url": "http://example.com", "token": "token"}
        )
        self.work = Work.objects.create(
            title="test",
            frbr_uri="/akn/za/act/2000/1",
            frbr_uri_country="za",
            frbr_uri_doctype="act",
            frbr_uri_date="2000",
            frbr_uri_number="1",
        )
        self.data = [
            {
                "work": "/akn/za/act/2000/1",
                "last_updated": "2023-10-01",
                "countries": [
                    {
                        "country": "ZA",
                        "ratification_date": "2023-09-01",
                        "deposit_date": "2023-09-01",
                        "signature_date": "2023-09-01",
                    },
                    {
                        "country": "XX",
                        "ratification_date": "2023-09-01",
                        "deposit_date": "2023-09-01",
                        "signature_date": "2023-09-01",
                    },
                ],
            }
        ]

    def test_create_ratifications(self):
        self.adapter.update_ratifications(self.data)
        self.assertEqual(
            ["/akn/za/act/2000/1"],
            [r.work.frbr_uri for r in Ratification.objects.all()],
        )
        ratification = Ratification.objects.first()
        self.assertEqual(["ZA"], [c.country.pk for c in ratification.countries.all()])
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.ratification_date for c in ratification.countries.all()],
        )
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.deposit_date for c in ratification.countries.all()],
        )
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.signature_date for c in ratification.countries.all()],
        )

    def test_update_ratifications(self):
        ratification = Ratification.objects.create(
            work=self.work, last_updated="2023-09-01"
        )
        RatificationCountry.objects.create(
            ratification=ratification,
            country=Country.objects.get(pk="ZA"),
            ratification_date="2020-01-01",
            deposit_date="2020-01-01",
            signature_date="2020-01-01",
        )

        self.adapter.update_ratifications(self.data)

        ratification.refresh_from_db()
        self.assertEqual(["ZA"], [c.country.pk for c in ratification.countries.all()])
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.ratification_date for c in ratification.countries.all()],
        )
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.deposit_date for c in ratification.countries.all()],
        )
        self.assertEqual(
            [datetime.date(2023, 9, 1)],
            [c.signature_date for c in ratification.countries.all()],
        )

    def test_create_ratifications_include_countries_without_country(self):
        self.adapter.include_countries = ["na"]
        self.adapter.update_ratifications(self.data)
        self.assertEqual(
            ["/akn/za/act/2000/1"],
            [r.work.frbr_uri for r in Ratification.objects.all()],
        )
        ratification = Ratification.objects.first()
        self.assertEqual([], [c.country.pk for c in ratification.countries.all()])

    def test_create_ratifications_include_countries_with_country(self):
        self.adapter.include_countries = ["za"]
        self.adapter.update_ratifications(self.data)
        self.assertEqual(
            ["/akn/za/act/2000/1"],
            [r.work.frbr_uri for r in Ratification.objects.all()],
        )
        ratification = Ratification.objects.first()
        self.assertEqual(["ZA"], [c.country.pk for c in ratification.countries.all()])

    def test_create_ratifications_exclude_countries_without_country(self):
        self.adapter.exclude_countries = ["na"]
        self.adapter.update_ratifications(self.data)
        self.assertEqual(
            ["/akn/za/act/2000/1"],
            [r.work.frbr_uri for r in Ratification.objects.all()],
        )
        ratification = Ratification.objects.first()
        self.assertEqual(["ZA"], [c.country.pk for c in ratification.countries.all()])

    def test_create_ratifications_exclude_countries_with_country(self):
        self.adapter.exclude_countries = ["za"]
        self.adapter.update_ratifications(self.data)
        self.assertEqual(
            ["/akn/za/act/2000/1"],
            [r.work.frbr_uri for r in Ratification.objects.all()],
        )
        ratification = Ratification.objects.first()
        self.assertEqual([], [c.country.pk for c in ratification.countries.all()])
