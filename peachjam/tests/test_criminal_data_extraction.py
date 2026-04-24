import datetime
import logging
import os
import unittest
from unittest.mock import patch

from countries_plus.models import Country
from django.db import IntegrityError, OperationalError, connections
from django.test import TransactionTestCase as TestCase
from languages_plus.models import Language

from peachjam.analysis.criminal_data.agent import (
    JUDGMENT_EXTRACTION_PROMPT,
    CaseMetaExtraction,
    JudgmentOffenceExtraction,
    JudgmentOutcomeExtraction,
    OffenceExtraction,
    OutcomeExtraction,
    SentenceExtraction,
    extract_case_type_filing_year,
    extract_offences_and_sentences,
    extract_outcomes,
)
from peachjam.analysis.criminal_data.agent import (
    search_offences_tool as search_offences,
)
from peachjam.analysis.criminal_data.extractor import CriminalDataExtractor
from peachjam.analysis.criminal_data.vocabulary import (
    JUDGMENT_OFFENCE_CASE_TAGS,
    normalize_tag_array,
)
from peachjam.models import (
    CaseTag,
    Court,
    Judgment,
    JudgmentOffence,
    Offence,
    OffenceCategory,
    OffenceTag,
    Outcome,
    Work,
)

log = logging.getLogger(__name__)


@unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class CriminalDataExtractionTests(TestCase):
    """
    Tests for the database search tool only.
    These do not call the LLM.
    """

    fixtures = [
        "offences/offences",
        "offences/penal_code_work",
    ]

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def setUp(self):
        self.robbery = Offence.objects.get(title="Robbery with violence")
        self.trespass = Offence.objects.get(title="Criminal trespass")
        Outcome.objects.get_or_create(name="Dismissed")
        Outcome.objects.get_or_create(name="Sentence reduced")

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
        of assault causing bodily harm and sentenced him to twelve months imprisonment.
        """.strip()

        result = extract_offences_and_sentences(judgment_text)
        log.info(f"test_extract_unmatched_offence_for_other_crime: {result}")

        extracted = " ".join(o.extracted_offence.lower() for o in result.offences)

        self.assertIn("assault", extracted)
        self.assertNotIn("robbery", extracted)
        self.assertNotIn("trespass", extracted)

        offence = result.offences[0]

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

    def test_extract_outcomes_for_split_result(self):
        judgment_text = """
        The appeal against conviction is dismissed.
        However, the sentence of ten years imprisonment is reduced to five years.
        """.strip()

        result = extract_outcomes(judgment_text)
        log.info("test_extract_outcomes_for_split_result: %s", result)

        self.assertTrue(result.outcomes)


class SearchOffencesTests(TestCase):
    def setUp(self):
        self.work = Work.objects.create(
            title="Test Work", frbr_uri="/akn/tz/act/2010/11"
        )

        self.abduction = Offence.objects.create(
            work=self.work,
            provision_eid="sec_1",
            code="ABD-1",
            title="Abduction",
            description=(
                "Taking away or detaining a woman against her will with intent to marry "
                "or have sexual intercourse with her."
            ),
        )

        self.abduction_of_girls = Offence.objects.create(
            work=self.work,
            provision_eid="sec_2",
            code="ABD-2",
            title="Abduction of girls under sixteen",
            description=(
                "A person who unlawfully takes an unmarried girl under the age of sixteen "
                "years out of lawful custody commits an offence."
            ),
        )

        self.assaults_causing_abh = Offence.objects.create(
            work=self.work,
            provision_eid="sec_3",
            code="ASS-3",
            title="Assaults causing actual bodily harm",
            description=(
                "A person who commits an assault that occasions actual bodily harm "
                "commits an offence under this provision."
            ),
        )

        self.attempt_armed_robbery = Offence.objects.create(
            work=self.work,
            provision_eid="sec_4",
            code="ROB-4",
            title="Attempt armed robbery",
            description=(
                "A person who, with intent to steal, is armed and threatens or attempts "
                "to threaten violence commits the offence of attempted armed robbery."
            ),
        )

        self.armed_robbery = Offence.objects.create(
            work=self.work,
            provision_eid="sec_5",
            code="ROB-5",
            title="Armed robbery",
            description=(
                "A person who steals and is armed with a dangerous or offensive weapon "
                "and uses or threatens violence commits armed robbery."
            ),
        )

        self.obtaining_goods_false_pretences = Offence.objects.create(
            work=self.work,
            provision_eid="sec_6",
            code="FRAUD-6",
            title="Obtaining goods by false pretences",
            description=(
                "A person who by false pretence and with intent to defraud obtains from "
                "another person anything capable of being stolen commits an offence."
            ),
        )

        self.obtaining_credit_false_pretences = Offence.objects.create(
            work=self.work,
            provision_eid="sec_7",
            code="FRAUD-7",
            title="Obtaining credit, etc., by false pretences",
            description=(
                "A person who by false pretence or other fraud obtains credit commits an offence."
            ),
        )

    def test_search_offences_empty_input_returns_empty_list(self):
        results = search_offences("")
        log.info("test_search_offences_empty_input_returns_empty_list: %s", results)

        self.assertEqual(results, [])

    def test_search_offences_abduction_returns_abduction_in_results(self):
        results = search_offences("abduction")
        log.info(
            "test_search_offences_abduction_returns_abduction_in_results: %s", results
        )

        titles = [r["title"] for r in results]

        self.assertIn("Abduction", titles)

    def test_search_offences_abduction_prefers_abduction_over_abduction_of_girls(self):
        results = search_offences("abduction")
        log.info(
            "test_search_offences_abduction_prefers_abduction_over_abduction_of_girls: %s",
            results,
        )

        self.assertTrue(results)
        self.assertEqual(results[0]["id"], self.abduction.id)

    def test_search_offences_assault_singular_matches_plural_title(self):
        results = search_offences("assault causing actual bodily harm")
        log.info(
            "test_search_offences_assault_singular_matches_plural_title: %s", results
        )

        titles = [r["title"].lower() for r in results]

        self.assertIn("assaults causing actual bodily harm", titles)

    def test_search_offences_attempted_armed_robbery_matches_attempt_title(self):
        results = search_offences("attempted armed robbery")
        log.info(
            "test_search_offences_attempted_armed_robbery_matches_attempt_title: %s",
            results,
        )

        titles = [r["title"].lower() for r in results]

        self.assertIn("attempt armed robbery", titles)

    def test_search_offences_false_pretences_returns_related_offences(self):
        results = search_offences("false pretences")
        log.info(
            "test_search_offences_false_pretences_returns_related_offences: %s", results
        )

        titles = [r["title"].lower() for r in results]

        self.assertIn("obtaining goods by false pretences", titles)
        self.assertIn("obtaining credit, etc., by false pretences", titles)

    def test_search_offences_multiple_terms_still_returns_abduction(self):
        results = search_offences("abduction, unlawful taking, taking away")
        log.info(
            "test_search_offences_multiple_terms_still_returns_abduction: %s", results
        )

        titles = [r["title"] for r in results]

        self.assertIn("Abduction", titles)

    def test_search_offences_returns_full_description(self):
        results = search_offences("abduction")
        log.info("test_search_offences_returns_full_description: %s", results)

        self.assertTrue(results)
        self.assertIn("description", results[0])
        self.assertTrue(results[0]["description"])

    def test_search_offences_results_are_stable_and_ordered(self):
        results = search_offences("abduction")
        log.info("test_search_offences_results_are_stable_and_ordered: %s", results)

        self.assertTrue(results)
        self.assertEqual(results[0]["title"], "Abduction")


class CriminalDataExtractorTests(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
        "offences/offences",
        "offences/penal_code_work",
    ]

    def setUp(self):
        self.judgment = Judgment.objects.create(
            case_name="Test criminal appeal",
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )
        self.robbery = Offence.objects.get(title="Robbery with violence")
        for case_tag_name in JUDGMENT_OFFENCE_CASE_TAGS:
            CaseTag.objects.get_or_create(name=case_tag_name)
        self.conviction_upheld = Outcome.objects.create(
            name="Conviction upheld",
            description="The conviction is affirmed on appeal.",
        )
        self.sentence_reduced = Outcome.objects.create(
            name="Sentence reduced",
            description="The sentence is reduced or varied downward.",
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch(
        "peachjam.analysis.criminal_data.extractor.CriminalDataExtractor.lock_judgment_for_extraction"
    )
    @patch("peachjam.analysis.criminal_data.extractor.extract_outcomes")
    @patch("peachjam.analysis.criminal_data.extractor.extract_offences_and_sentences")
    @patch("peachjam.analysis.criminal_data.extractor.extract_case_type_filing_year")
    @patch("peachjam.models.core_document.CoreDocument.get_content_as_text")
    def test_extractor_skips_when_judgment_lock_is_busy(
        self,
        mock_get_content_as_text,
        mock_extract_case_type_filing_year,
        mock_extract_offences_and_sentences,
        mock_extract_outcomes,
        mock_lock_judgment_for_extraction,
    ):
        mock_lock_judgment_for_extraction.side_effect = OperationalError(
            "could not obtain lock on row"
        )

        CriminalDataExtractor().extract(self.judgment)

        self.assertFalse(mock_get_content_as_text.called)
        self.assertFalse(mock_extract_case_type_filing_year.called)
        self.assertFalse(mock_extract_offences_and_sentences.called)
        self.assertFalse(mock_extract_outcomes.called)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("peachjam.analysis.criminal_data.extractor.extract_outcomes")
    @patch("peachjam.analysis.criminal_data.extractor.extract_offences_and_sentences")
    @patch("peachjam.analysis.criminal_data.extractor.extract_case_type_filing_year")
    @patch("peachjam.models.core_document.CoreDocument.get_content_as_text")
    def test_extractor_sets_canonical_outcomes(
        self,
        mock_get_content_as_text,
        mock_extract_case_type_filing_year,
        mock_extract_offences_and_sentences,
        mock_extract_outcomes,
    ):
        mock_get_content_as_text.return_value = "Criminal appeal text"
        mock_extract_case_type_filing_year.return_value = CaseMetaExtraction(
            case_type="criminal",
            filing_year=2019,
        )
        mock_extract_offences_and_sentences.return_value = JudgmentOffenceExtraction(
            offences=[
                OffenceExtraction(
                    offence_id=self.robbery.id,
                    extracted_offence="robbery with violence",
                    case_tags=[],
                    sentences=[
                        SentenceExtraction(
                            sentence_type="imprisonment",
                            duration_months=120,
                            fine_amount=None,
                            suspended=False,
                            mandatory_minimum=None,
                        )
                    ],
                )
            ]
        )
        mock_extract_outcomes.return_value = JudgmentOutcomeExtraction(
            outcomes=[
                OutcomeExtraction(
                    extracted_outcome="Conviction upheld",
                ),
                OutcomeExtraction(
                    extracted_outcome="Sentence reduced",
                ),
            ]
        )

        CriminalDataExtractor().extract(self.judgment)
        self.judgment.refresh_from_db()

        self.assertEqual(self.judgment.case_type, Judgment.CaseType.CRIMINAL)
        self.assertEqual(self.judgment.filing_year, 2019)
        self.assertCountEqual(
            self.judgment.outcomes.values_list("id", flat=True),
            [self.conviction_upheld.id, self.sentence_reduced.id],
        )
        self.assertEqual(self.judgment.judgment_offence.count(), 1)
        self.assertEqual(self.judgment.sentences.count(), 1)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("peachjam.analysis.criminal_data.extractor.extract_outcomes")
    @patch("peachjam.analysis.criminal_data.extractor.extract_offences_and_sentences")
    @patch("peachjam.analysis.criminal_data.extractor.extract_case_type_filing_year")
    @patch("peachjam.models.core_document.CoreDocument.get_content_as_text")
    def test_extractor_clears_outcomes_for_non_criminal_case(
        self,
        mock_get_content_as_text,
        mock_extract_case_type_filing_year,
        mock_extract_offences_and_sentences,
        mock_extract_outcomes,
    ):
        self.judgment.outcomes.add(self.conviction_upheld, self.sentence_reduced)

        mock_get_content_as_text.return_value = "Civil appeal text"
        mock_extract_case_type_filing_year.return_value = CaseMetaExtraction(
            case_type="civil",
            filing_year=2020,
        )

        CriminalDataExtractor().extract(self.judgment)
        self.judgment.refresh_from_db()

        self.assertEqual(self.judgment.case_type, Judgment.CaseType.CIVIL)
        self.assertEqual(self.judgment.filing_year, 2020)
        self.assertEqual(self.judgment.outcomes.count(), 0)
        self.assertFalse(mock_extract_offences_and_sentences.called)
        self.assertFalse(mock_extract_outcomes.called)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch("peachjam.analysis.criminal_data.extractor.extract_outcomes")
    @patch("peachjam.analysis.criminal_data.extractor.extract_offences_and_sentences")
    @patch("peachjam.analysis.criminal_data.extractor.extract_case_type_filing_year")
    @patch("peachjam.models.core_document.CoreDocument.get_content_as_text")
    def test_extractor_persists_normalized_case_tags_and_drops_invalid(
        self,
        mock_get_content_as_text,
        mock_extract_case_type_filing_year,
        mock_extract_offences_and_sentences,
        mock_extract_outcomes,
    ):
        mock_get_content_as_text.return_value = "Criminal appeal text"
        mock_extract_case_type_filing_year.return_value = CaseMetaExtraction(
            case_type="criminal",
            filing_year=2019,
        )
        mock_extract_offences_and_sentences.return_value = JudgmentOffenceExtraction(
            offences=[
                OffenceExtraction(
                    offence_id=self.robbery.id,
                    extracted_offence="robbery with violence",
                    case_tags=[
                        " Weapon-Used ",
                        "group-offending",
                        "weapon-used",
                        "",
                        "unknown-tag",
                    ],
                    sentences=[],
                )
            ]
        )
        mock_extract_outcomes.return_value = JudgmentOutcomeExtraction(outcomes=[])

        with self.assertLogs(
            "peachjam.analysis.criminal_data.extractor", level="INFO"
        ) as logs:
            CriminalDataExtractor().extract(self.judgment)

        jo = self.judgment.judgment_offence.get()
        self.assertEqual(
            list(jo.tags.values_list("name", flat=True)),
            ["group-offending", "weapon-used"],
        )
        self.assertTrue(
            any("dropping invalid case tags" in message for message in logs.output)
        )
        self.assertTrue(any("with case tags" in message for message in logs.output))


class CriminalDataVocabularyTests(TestCase):
    def test_normalize_tag_array_lowercases_trims_deduplicates_and_drops_blanks(self):
        self.assertEqual(
            normalize_tag_array(
                [" Weapon-Used ", "", "weapon-used", " group-offending ", None]
            ),
            ["weapon-used", "group-offending"],
        )

    def test_normalize_tag_array_rejects_unknown_tags_when_validation_requested(self):
        with self.assertRaises(ValueError):
            normalize_tag_array(
                ["weapon-used", "not-a-real-tag"],
                allowed_tags=JUDGMENT_OFFENCE_CASE_TAGS,
                validate=True,
            )

    def test_normalize_tag_array_preserves_input_order_after_cleaning(self):
        self.assertEqual(
            normalize_tag_array(
                [
                    " threats-used ",
                    "weapon-used",
                    "threats-used",
                    "group-offending",
                ],
                allowed_tags=JUDGMENT_OFFENCE_CASE_TAGS,
            ),
            ["threats-used", "weapon-used", "group-offending"],
        )


class CriminalDataModelTests(TestCase):
    fixtures = [
        "tests/countries",
        "tests/courts",
        "tests/languages",
    ]

    def setUp(self):
        self.work = Work.objects.create(
            title="Test Work", frbr_uri="/akn/za/act/2001/1"
        )
        self.judgment = Judgment.objects.create(
            case_name="Test criminal appeal",
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.get(pk="en"),
            jurisdiction=Country.objects.get(pk="ZA"),
        )

    def test_offence_category_slug_auto_populates(self):
        category = OffenceCategory.objects.create(name="Public Safety")
        self.assertEqual(category.slug, "public-safety")

    def test_offence_tag_name_is_unique(self):
        OffenceTag.objects.create(name="weapon-capable")

        with self.assertRaises(IntegrityError):
            OffenceTag.objects.create(name="weapon-capable")

    def test_case_tag_name_is_unique(self):
        CaseTag.objects.create(name="weapon-used")

        with self.assertRaises(IntegrityError):
            CaseTag.objects.create(name="weapon-used")

    def test_offence_is_unique_by_work_and_provision_eid(self):
        Offence.objects.create(
            work=self.work,
            provision_eid="sec_1",
            code="A-1",
            title="First offence",
        )

        with self.assertRaises(IntegrityError):
            Offence.objects.create(
                work=self.work,
                provision_eid="sec_1",
                code="A-2",
                title="Second offence",
            )

    def test_judgment_offence_is_unique_by_judgment_and_offence(self):
        offence = Offence.objects.create(
            work=self.work,
            provision_eid="sec_2",
            code="B-1",
            title="Robbery",
        )
        JudgmentOffence.objects.create(judgment=self.judgment, offence=offence)

        with self.assertRaises(IntegrityError):
            JudgmentOffence.objects.create(judgment=self.judgment, offence=offence)

    def test_offence_tags_many_to_many(self):
        offence = Offence.objects.create(
            work=self.work,
            provision_eid="sec_3",
            code="C-1",
            title="Attempted robbery",
        )
        offence.tags.set(
            [
                OffenceTag.objects.create(name="weapon-capable"),
                OffenceTag.objects.create(name="inchoate"),
            ]
        )

        self.assertEqual(
            list(offence.tags.values_list("name", flat=True)),
            ["inchoate", "weapon-capable"],
        )

    def test_judgment_offence_tags_many_to_many(self):
        offence = Offence.objects.create(
            work=self.work,
            provision_eid="sec_4",
            code="D-1",
            title="Robbery",
        )
        judgment_offence = JudgmentOffence.objects.create(
            judgment=self.judgment,
            offence=offence,
        )
        judgment_offence.tags.set(
            [
                CaseTag.objects.create(name="weapon-used"),
                CaseTag.objects.create(name="group-offending"),
            ]
        )

        self.assertEqual(
            list(judgment_offence.tags.values_list("name", flat=True)),
            ["group-offending", "weapon-used"],
        )


class CriminalDataPromptTests(TestCase):
    def test_offence_extraction_supports_case_tags(self):
        extraction = OffenceExtraction(
            offence_id=1,
            extracted_offence="robbery with violence",
            case_tags=["weapon-used", "group-offending"],
            sentences=[],
        )

        self.assertEqual(extraction.case_tags, ["weapon-used", "group-offending"])

    def test_prompt_includes_case_tag_guidance_and_examples(self):
        self.assertIn("Allowed case tags only:", JUDGMENT_EXTRACTION_PROMPT)
        self.assertIn("consent-disputed", JUDGMENT_EXTRACTION_PROMPT)
        self.assertIn("group-offending", JUDGMENT_EXTRACTION_PROMPT)
        self.assertIn("weapon-used", JUDGMENT_EXTRACTION_PROMPT)
        self.assertIn("Do not infer `consent-disputed`", JUDGMENT_EXTRACTION_PROMPT)
        self.assertIn("do not add `weapon-used`", JUDGMENT_EXTRACTION_PROMPT)
