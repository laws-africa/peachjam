import datetime

from countries_plus.models import Country
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import DocumentNature, LegalInstrument


class BaseDocumentFilterFormTestCase(TestCase):
    fixtures = ["documents/sample_documents", "tests/countries", "tests/languages"]
    maxDiff = None

    def test_years_filter(self):
        # single year
        response = self.client.get("/legal_instruments/?years=2007")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["facet_data"]["years"], [2007])

        # multiple years
        legal_instrument = LegalInstrument(
            title="African Civil Aviation Commission Constitution (AFCAC)",
            language=Language.objects.get(pk="en"),
            date=datetime.date(2022, 10, 17),
            jurisdiction=Country.objects.get(pk="ZA"),
            frbr_uri_doctype="act",
            frbr_uri_actor="nick",
            frbr_uri_date="2022",
            frbr_uri_number="civil-aviation-commission",
            nature=DocumentNature.objects.get(pk=8),
        )

        legal_instrument_1 = LegalInstrument(
            title="African Charter on Democracy, Elections and Governance",
            language=Language.objects.get(pk="en"),
            date=datetime.date(1990, 10, 17),
            jurisdiction=Country.objects.get(pk="ZA"),
            frbr_uri_doctype="act",
            frbr_uri_actor="nick",
            frbr_uri_date="1990",
            frbr_uri_number="democracy-elections-and-governance",
            nature=DocumentNature.objects.get(pk=8),
        )

        legal_instrument_2 = LegalInstrument(
            title="African Charter on Elections, Democracy and Governance",
            language=Language.objects.get(pk="en"),
            date=datetime.date(1972, 10, 17),
            jurisdiction=Country.objects.get(pk="ZA"),
            frbr_uri_doctype="act",
            frbr_uri_actor="nick",
            frbr_uri_date="1972",
            frbr_uri_number="elections-democracy-and-governance",
            nature=DocumentNature.objects.get(pk=8),
        )
        legal_instrument.save()
        legal_instrument_1.save()
        legal_instrument_2.save()

        response = self.client.get(
            "/legal_instruments/?years=2022&years=1990&years=1972&years=2007"
        )
        documents = response.context.get("documents")

        self.assertEqual(response.status_code, 200)
        self.assertIn(legal_instrument, documents)
        self.assertIn(legal_instrument_1, documents)
        self.assertIn(legal_instrument_2, documents)
        self.assertEqual(
            response.context["facet_data"]["years"], [2022, 1972, 1990, 2007]
        )
