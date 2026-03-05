import os
import unittest

from django.test import TestCase

from peachjam.analysis.criminal_data.agent import extract_offences_and_sentences
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
