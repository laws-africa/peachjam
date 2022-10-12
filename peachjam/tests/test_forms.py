import datetime

from countries_plus.models import Country
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import LegalInstrument


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["documents/sample_documents", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_years_filter(self):
        legal_instrument = LegalInstrument(
            language=Language.objects.get(pk="en"),
            date=datetime.date(2022, 10, 17),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        legal_instrument.save()

        # response = self.client.get("/legal_instruments/?years=2022")
