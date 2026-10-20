from datetime import date

from countries_plus.models import Country
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from languages_plus.models import Language

from peachjam.models import Gazette
from peachjam.views.gazette import year_and_month_aggs


class GazetteAggregationTest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        self.country = Country.objects.get(pk="AA")
        self.language = Language.objects.get(pk="en")

    def create_gazette(self, gazette_date, number):
        return Gazette.objects.create(
            jurisdiction=self.country,
            language=self.language,
            date=gazette_date,
            frbr_uri_number=number,
            title=f"Gazette {number}",
            published=True,
        )

    def test_year_and_month_aggs_groups_in_the_database(self):
        self.create_gazette(date(2024, 1, 1), "1")
        self.create_gazette(date(2024, 1, 2), "2")
        self.create_gazette(date(2024, 2, 1), "3")
        self.create_gazette(date(2023, 12, 1), "4")

        with CaptureQueriesContext(connection) as queries:
            results = year_and_month_aggs(Gazette.objects.all())

        self.assertEqual(1, len(queries))
        self.assertIn("GROUP BY 1, 2", queries[0]["sql"])
        self.assertEqual([2024, 2023], [item["year"] for item in results])
        self.assertEqual([3, 1], [item["count"] for item in results])
        self.assertEqual([2, 1], [month["count"] for month in results[0]["months"][:2]])
