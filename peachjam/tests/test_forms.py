from datetime import date

from countries_plus.models import Country
from django.test import TestCase

from peachjam.models import CoreDocument, LegalInstrument, Locality


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["tests/countries"]
    maxDiff = None

    def test_years_filter(self):
        legal_instrument = LegalInstrument(
            jurisdiction=Country.objects.get(pk="ZA"),
            doc_type="legal_instrument",
            date=date(2005, 12, 22),
            frbr_uri_doctype="act",
            frbr_uri_date="2016-11-04",
            frbr_uri_number="adipisci-excepturi-pariatur-eum-magnam",
            coredocument_ptr_id=CoreDocument.objects.get(pk=15),
            locality=Locality.objects.get(pk=1),
        )
        legal_instrument.save()
        legal_instrument.refresh_from_db()

        # response = self.client.get("/legal_instruments/?years=2005")
