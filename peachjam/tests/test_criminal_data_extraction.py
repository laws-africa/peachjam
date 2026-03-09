import logging
import os
import unittest

from django.db import connections
from django.test import TransactionTestCase as TestCase

from peachjam.analysis.criminal_data.agent import (
    extract_case_type_filing_year,
    extract_offences_and_sentences,
)
from peachjam.models import Offence, Work

log = logging.getLogger(__name__)


@unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class CriminalDataExtractionTests(TestCase):
    """
    Tests for the database search tool only.
    These do not call the LLM.
    """

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def setUp(self):
        Work.objects.create(title="Test Work", frbr_uri="/akn/tz/act/2010/11")
        self.robbery = Offence.objects.create(
            work=Work.objects.first(),
            title="Robbery with violence",
            description="""
            A person who steals anything and, at or immediately before or after the time of stealing it,
            uses or threatens to use actual violence to any person or property in order to obtain or retain
            the thing stolen or to prevent or overcome resistance to its being stolen
            or retained, commits robbery.
            """,
        )

        self.trespass = Offence.objects.create(
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
        judgment_text = """
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

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_robbery_with_violence: {result}")

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

    def test_extract_trespass(self):
        judgment_text = """
        The appellant was charged with criminal trespass contrary to section 5 of the Trespass Act.
        The prosecution evidence established that on the night of 12th June 2019 the appellant unlawfully entered the
        complainant's fenced compound without permission and refused to leave when ordered to do so.
        The trial court found the appellant guilty of criminal trespass and sentenced him to six months imprisonment.
        Being dissatisfied with the conviction and sentence, the appellant lodged the present appeal.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_trespass: {result}")

        self.assertTrue(result.offences)

        offence = result.offences[0]

        self.assertEqual(offence.offence_id, self.trespass.id)
        self.assertIn("trespass", offence.extracted_offence.lower())
        self.assertNotIn("robbery", offence.extracted_offence.lower())

        self.assertTrue(offence.sentences)

        sentence = offence.sentences[0]

        self.assertEqual(sentence.sentence_type, "imprisonment")

        expected_months = 6
        self.assertEqual(sentence.duration_months, expected_months)

    def test_extract_multiple_offences_and_values(self):
        judgment_text = """
         The accused person faced two charges before the trial court.
         Count I was criminal trespass contrary to section 5 of the Trespass Act.
         Count II was robbery with violence contrary to section 296(2) of the Penal Code.

         After evaluating the evidence, the trial court convicted the accused on both counts.

         On the first count of criminal trespass, the court fined the accused KSh 20,000
         in default to serve three months imprisonment.

         On the second count of robbery with violence, the court observed that the law prescribes a
         mandatory minimum sentence. The accused was therefore sentenced to ten years imprisonment as required by law.
         """

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_multiple_offences: {result}")

        self.assertTrue(result.offences)

        offence_ids = [o.offence_id for o in result.offences]

        self.assertGreaterEqual(len(result.offences), 2)
        self.assertIn(self.trespass.id, offence_ids)
        self.assertIn(self.robbery.id, offence_ids)

        trespass = next(o for o in result.offences if o.offence_id == self.trespass.id)
        self.assertIn("trespass", trespass.extracted_offence.lower())
        self.assertTrue(trespass.sentences)

        trespass_sentence_types = [s.sentence_type for s in trespass.sentences]
        self.assertIn("fine", trespass_sentence_types)

        trespass_fine = next(s for s in trespass.sentences if s.sentence_type == "fine")
        self.assertEqual(trespass_fine.fine_amount, 20000)

        robbery = next(o for o in result.offences if o.offence_id == self.robbery.id)
        self.assertIn("robbery", robbery.extracted_offence.lower())
        self.assertTrue(robbery.sentences)

        robbery_imprisonment = next(
            s for s in robbery.sentences if s.sentence_type == "imprisonment"
        )
        self.assertEqual(robbery_imprisonment.duration_months, 120)
        self.assertTrue(robbery_imprisonment.mandatory_minimum is True)

    def test_extract_unmatched_offence_for_other_crime(self):
        judgment_text = """
        The appellant was charged with assault causing actual bodily harm.

        The prosecution evidence was that the appellant attacked the complainant
        during a quarrel and caused bodily injuries.

        After hearing the evidence, the trial court convicted the appellant
        of assault and sentenced him to twelve months imprisonment.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_unmatched_offence_for_other_crime: {result}")

        extracted = " ".join(o.extracted_offence.lower() for o in result.offences)

        self.assertIn("assault", extracted)
        self.assertNotIn("robbery", extracted)
        self.assertNotIn("trespass", extracted)

        offence = result.offences[0]
        self.assertIsNone(offence.offence_id)

        sentence = offence.sentences[0]
        self.assertEqual(sentence.sentence_type, "imprisonment")
        self.assertEqual(sentence.duration_months, 12)

    def test_extract_no_offences_for_civil_judgment(self):
        judgment_text = """
        IN THE HIGH COURT OF TANZANIA
        AT DAR ES SALAAM
        CIVIL APPEAL NO. 8 OF 2021

        The appellant challenges the judgment of the lower court on liability
        and damages arising from breach of contract.

        After considering the record and submissions, the court dismisses the appeal.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_no_offences_for_civil_judgment: {result}")

        self.assertEqual(result.offences, [])

    def test_extract_unmatched_offence_for_incidental_mentions_only(self):
        judgment_text = """
        The appellant was charged with assault.

        In his submissions, counsel cited authorities discussing robbery with violence
        and criminal trespass as examples of offences requiring strict proof.

        However, in the present case the appellant was only charged with assault
        and was sentenced to six months imprisonment.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(
            f"test_extract_unmatched_offence_for_incidental_mentions_only: {result}"
        )

        extracted = " ".join(o.extracted_offence.lower() for o in result.offences)

        self.assertIn("assault", extracted)
        self.assertNotIn("robbery", extracted)
        self.assertNotIn("trespass", extracted)

        offence = result.offences[0]
        self.assertIsNone(offence.offence_id)

        sentence = offence.sentences[0]
        self.assertEqual(sentence.duration_months, 6)

    def test_extract_unclear_text_does_not_match_seeded_offences(self):
        judgment_text = """
        The appellant was convicted and sentenced by the trial court.

        He now appeals against both conviction and sentence, arguing that
        the prosecution failed to prove the case beyond reasonable doubt.

        The court has considered the record and submissions of the parties.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_unclear_text_does_not_match_seeded_offences: {result}")

        extracted = " ".join(o.extracted_offence.lower() for o in result.offences)

        self.assertNotIn("robbery", extracted)
        self.assertNotIn("trespass", extracted)

    def test_extract_criminal_case_type_and_filing_year(self):
        CRIMINAL_TEXT_WITH_FILING_YEAR = """
        IN THE HIGH COURT OF TANZANIA
        AT ARUSHA
        CRIMINAL APPEAL NO. 12 OF 2019

        The appellant was convicted of robbery with violence contrary to section 296(2)
        of the Penal Code and sentenced to twenty years imprisonment.
        """.strip()

        expected_case_type = "criminal"
        expected_filing_year = 2019

        result = extract_case_type_filing_year(CRIMINAL_TEXT_WITH_FILING_YEAR)
        log.info(f"test_extract_criminal_case_type_and_filing_year: {result}")

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)

    def test_extract_civil_case_type_and_filing_year(self):
        CIVIL_TEXT_WITH_FILING_YEAR = """
        IN THE HIGH COURT OF TANZANIA
        AT DAR ES SALAAM
        CIVIL APPEAL NO. 3 OF 2020

        The appellant challenges the award of general damages for breach of contract.
        """.strip()

        expected_case_type = "civil"
        expected_filing_year = 2020

        result = extract_case_type_filing_year(CIVIL_TEXT_WITH_FILING_YEAR)
        log.info(f"test_extract_civil_case_type_and_filing_year: {result}")

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)

    def test_extract_unknown_when_unclear(self):
        UNCLEAR_TEXT = """
        The matter came up for hearing. The court considered the submissions and delivered judgment.
        """.strip()

        expected_case_type = None
        expected_filing_year = None

        result = extract_case_type_filing_year(UNCLEAR_TEXT)
        log.info(f"test_extract_unknown_case_type: {result}")

        self.assertEqual(result.case_type, expected_case_type)
        self.assertEqual(result.filing_year, expected_filing_year)
