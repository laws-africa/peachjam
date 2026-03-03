import os
import unittest

from django.test import TestCase

from peachjam.analysis.criminal_data import SentenceExtractor
from peachjam.analysis.criminal_data.extractor import CriminalDataExtractor
from peachjam.analysis.criminal_data.offence import (
    OffenceMatcher,
    OffenceMentionExtractor,
)
from peachjam.analysis.criminal_data.offence_tool import OffenceToolMatcher
from peachjam.models import Judgment, JudgmentOffence, Offence, Sentence


@unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class CriminalDataExtractionTests(TestCase):
    fixtures = [
        "tests/courts",
        "tests/countries",
        "tests/languages",
        "tests/extraction_judgment",
    ]

    def setUp(self):
        self.judgment = Judgment.objects.get(pk=990010)
        self.robbery = Offence.objects.get(pk=990101)
        self.housebreaking = Offence.objects.get(pk=990102)

    def assert_offence_links_created(self):
        self.assertQuerySetEqual(
            JudgmentOffence.objects.filter(judgment=self.judgment)
            .order_by("offence_id")
            .values_list("offence_id", flat=True),
            [self.robbery.id, self.housebreaking.id],
            transform=lambda x: x,
        )

    def test_offence_mention_extractor(self):
        offences = OffenceMentionExtractor(self.judgment).run()

        self.assertIn("robbery with violence", offences)
        self.assertIn("housebreaking", offences)

    def test_offence_matcher(self):
        OffenceMentionExtractor(self.judgment).run()
        OffenceMatcher(self.judgment).run()

        self.assert_offence_links_created()

    def test_sentence_extractor(self):
        JudgmentOffence.objects.create(judgment=self.judgment, offence=self.robbery)
        JudgmentOffence.objects.create(
            judgment=self.judgment, offence=self.housebreaking
        )

        SentenceExtractor(self.judgment).run()

        self.assertEqual(2, Sentence.objects.filter(judgment=self.judgment).count())
        self.assertTrue(
            Sentence.objects.filter(
                judgment=self.judgment,
                sentence_type=Sentence.SentenceType.IMPRISONMENT,
                duration_months=120,
            ).exists()
        )
        self.assertTrue(
            Sentence.objects.filter(
                judgment=self.judgment,
                sentence_type=Sentence.SentenceType.FINE,
                fine_amount=5000,
            ).exists()
        )

    def test_offence_tool_matcher(self):
        OffenceToolMatcher(self.judgment).run()

        self.assert_offence_links_created()

    def test_full_extraction_pipeline(self):
        CriminalDataExtractor(self.judgment).run()

        self.judgment.refresh_from_db()

        self.assertEqual(Judgment.CaseType.CRIMINAL, self.judgment.case_type)
        self.assertEqual(2021, self.judgment.filing_year)
        self.assert_offence_links_created()
        self.assertTrue(Sentence.objects.filter(judgment=self.judgment).exists())
