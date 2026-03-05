import os
import unittest

from django.test import TestCase

from peachjam.analysis.criminal_data.agent import (
    extract_case_type_filing_year,
    extract_offences_and_sentences,
)
from peachjam.models import Offence, Work

JUDGMENT_TEXT = """
The appellant, John Mrema, was convicted of robbery with violence
contrary to section 296(2) of the Penal Code.

The prosecution alleged that on the night of 14th March 2019 at
Moshi town, the appellant together with others not before court
robbed the complainant of a mobile phone and cash while armed
with a knife and threatened to use violence.

After hearing the evidence, the trial court found the appellant
guilty of the offence of robbery with violence and sentenced him
to twenty years imprisonment.

Being dissatisfied with the conviction and sentence, the appellant
filed the present appeal challenging both conviction and sentence.
""".strip()


@unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class SearchOffencesTests(TestCase):
    """
    Tests for the database search tool only.
    These do not call the LLM.
    """

    fixtures = [
        "tests/courts",
        "tests/countries",
        "tests/languages",
        "tests/extraction_judgment",
        "documents/sample_documents",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.robbery = Offence.objects.create(
            work=Work.objects.first(),
            title="Robbery with violence",
            description="""
            A person who steals anything and, at or immediately before or after the time of stealing it,
            uses or threatens to use actual violence to any person or property in order to obtain or retain
            the thing stolen or to prevent or overcome resistance to its being stolen
            or retained, commits robbery.
            """,
        )

        cls.trespass = Offence.objects.create(
            work=Work.objects.first(),
            title="Criminal trespass",
            description="""
            A person who unlawfully enters into or upon property in the possession of another with "
            intent to commit an offence or to intimidate, insult or annoy any person in possession of
            the property, or who, having lawfully entered, unlawfully remains there with such intent,
            commits criminal trespass.
            """,
        )

    def test_extract_robbery_with_violence(self):

        result = extract_offences_and_sentences(JUDGMENT_TEXT)

        self.assertTrue(result.offences)

        offence = result.offences[0]

        self.assertEqual(offence.offence_id, self.robbery.id)
        self.assertIn("robbery", offence.extracted_offence.lower())
        self.assertNotIn("trespass", offence.extracted_offence.lower())

        self.assertTrue(offence.sentences)

        sentence = offence.sentences[0]

        self.assertEqual(sentence.sentence_type, "imprisonment")

        expected_months = 240  # 20 years -> 240 months
        self.assertEqual(sentence.duration_months, expected_months)


CRIMINAL_TEXT_WITH_FILING_YEAR = """
IN THE HIGH COURT OF TANZANIA
AT ARUSHA
CRIMINAL APPEAL NO. 12 OF 2019

The appellant was convicted of robbery with violence contrary to section 296(2)
of the Penal Code and sentenced to twenty years imprisonment.
""".strip()

CIVIL_TEXT_WITH_FILING_YEAR = """
IN THE HIGH COURT OF TANZANIA
AT DAR ES SALAAM
CIVIL APPEAL NO. 3 OF 2020

The appellant challenges the award of general damages for breach of contract.
""".strip()

UNCLEAR_TEXT = """
The matter came up for hearing. The court considered the submissions and delivered judgment.
""".strip()


class CaseTypeFilingYearExtractionTests(TestCase):
    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
    def test_extract_criminal_case_type_and_filing_year(self):
        expected_case_type = "criminal"
        expected_filing_year = 2019

        result = extract_case_type_filing_year(CRIMINAL_TEXT_WITH_FILING_YEAR)

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)
        self.assertLessEqual(len(result.basis.split()), 25)

    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
    def test_extract_civil_case_type_and_filing_year(self):
        expected_case_type = "civil"
        expected_filing_year = 2020

        result = extract_case_type_filing_year(CIVIL_TEXT_WITH_FILING_YEAR)

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)
        self.assertLessEqual(len(result.basis.split()), 25)

    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
    def test_extract_unknown_when_unclear(self):
        expected_case_type = None
        expected_filing_year = None

        result = extract_case_type_filing_year(UNCLEAR_TEXT)

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)
        self.assertLessEqual(len(result.basis.split()), 25)
