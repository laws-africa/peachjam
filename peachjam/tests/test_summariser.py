import datetime
import os
import unittest
from unittest.mock import MagicMock, patch

from countries_plus.models import Country
from django.conf import settings
from django.test import TransactionTestCase as TestCase
from django.test import override_settings
from languages_plus.models import Language

from peachjam.analysis.summariser import JudgmentSummariser, JudgmentSummary
from peachjam.models import Court, Flynote, FlynoteDocumentCount, Judgment

MATCH_FLYNOTES_TEST_INPUT = [
    {
        "role": "user",
        "content": (
            "Summarise this judgment and generate a flynote. "
            "The judgment concerns post-judgment interest under the PRIA and "
            "the RAF Act."
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Issues:\n"
            "- Whether s 2(1) PRIA creates ex lege interest on judgment debts arising "
            "from unliquidated claims.\n"
            "- How s 2(1) PRIA interacts with s 17(3)(a) of the RAF Act.\n\n"
            "Held:\n"
            "- The court considered the statutory basis for post-judgment interest.\n"
            "- The court considered the interaction between the PRIA and the RAF Act.\n\n"
            "Order: Appeal dismissed.\n\n"
            "Summary: The court dealt with post-judgment interest on RAF judgment debts.\n\n"
            "Flynote: Civil procedure — Post judgment interest — Whether s 2(1) PRIA creates "
            "ex lege interest on judgment debts arising from unliquidated claims — Interaction "
            "with s 17(3)(a) RAF Act\n\n"
            "Blurb: Post-judgment interest under the PRIA and RAF Act."
        ),
    },
]

ROOTS = """
Civil procedure
Criminal law
Land law
Evidence
Criminal procedure
"""


@unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
class JudgmentSummariserE2ETest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]
    maxDiff = None

    def setUp(self):
        self.get_prompt_patcher = patch(
            "peachjam.analysis.summariser.langfuse.get_prompt",
            return_value=None,
        )
        self.get_prompt_patcher.start()
        self.addCleanup(self.get_prompt_patcher.stop)

        for root in ROOTS.strip().splitlines():
            root = root.strip()
            Flynote.add_root(name=root)

        self.summariser = JudgmentSummariser()
        self.summariser.match_flynotes_to_db = True
        self.summariser.summary_prompt_str = (
            "You are continuing a judgment summarisation workflow. "
            "Follow the latest developer instructions exactly and return the requested output."
        )
        self.summariser.llm_model = "gpt-5-mini"
        self.summariser.create_agent("South Africa")

        self.summariser.run_result = MagicMock()
        self.summariser.run_result.to_input_list.return_value = (
            MATCH_FLYNOTES_TEST_INPUT
        )

    def test_match_flynotes_end_to_end(self):
        # The proposed flynote intentionally uses a non-database variation for component 2:
        # "Post judgment interest" instead of "Post-judgment interest".
        summary = JudgmentSummary(
            issues=[
                "Whether s 2(1) PRIA creates ex lege interest on judgment debts arising from unliquidated claims."
            ],
            held=[
                "The court considered the interaction between the PRIA and the RAF Act."
            ],
            order="Appeal dismissed.",
            summary="The court dealt with post-judgment interest on RAF judgment debts.",
            flynote=(
                "Civil procedure — Post judgment interest — Whether s 2(1) PRIA creates "
                "ex lege interest on judgment debts arising from unliquidated claims — "
                "Interaction with s 17(3)(a) RAF Act"
            ),
            blurb="Post-judgment interest under the PRIA and RAF Act.",
        )

        self.civil_procedure = Flynote.objects.get(name="Civil procedure")
        FlynoteDocumentCount.objects.create(flynote=self.civil_procedure, count=640)
        # The AI should select this root for component 1 from the top-level prompt.
        self.post_judgment_interest = self.civil_procedure.add_child(
            name="Post-judgment interest",
        )
        FlynoteDocumentCount.objects.create(
            flynote=self.post_judgment_interest,
            count=320,
        )
        # The AI should normalize "Post judgment interest" to this database entry for component 2.
        self.unrelated_child = self.post_judgment_interest.add_child(
            name="Taxation of costs",
        )
        FlynoteDocumentCount.objects.create(
            flynote=self.unrelated_child,
            count=180,
        )
        # There is no relevant child under the chosen component 2, so the AI should keep its
        # original component 3 and component 4 wording.

        result = self.summariser.match_flynotes(summary)

        self.assertTrue(result.flynote)
        self.assertEqual(
            result.flynote,
            "Civil procedure — Post-judgment interest — Whether s 2(1) PRIA creates "
            "ex lege interest on judgment debts arising from unliquidated claims — "
            "Interaction with s 17(3)(a) RAF Act",
        )

    @unittest.mock.patch.dict(
        os.environ,
        {
            "LANGFUSE_PUBLIC_KEY": "test-langfuse-public-key",
            "LANGFUSE_SECRET_KEY": "test-langfuse-secret-key",
        },
        clear=False,
    )
    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SUMMARISE_JUDGMENTS": True,
        }
    )
    def test_summarise_judgment_returns_non_empty_fields(self):
        judgment = Judgment.objects.create(
            case_name="Test judgment for AI summary",
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )
        doc_content = judgment.get_or_create_document_content(True)
        doc_content.set_content_html("""
            <p>The appellant sought leave to appeal out of time after failing to comply with the
            prescribed rules. The High Court considered the explanation for the delay, the
            prospects of success, and the interests of justice.</p>
            <p>The court found that the delay had not been adequately explained and that the
            proposed appeal lacked sufficient prospects of success. The application was dismissed
            with costs.</p>
            """)
        doc_content.save()

        summariser = JudgmentSummariser()
        summariser.match_flynotes_to_db = False
        summariser.llm_model = "gpt-5-mini"
        summariser.summary_prompt_str = (
            "You are summarising a court judgment for legal research. Return concise but "
            "substantive values for issues, held, order, summary, flynote, and blurb."
        )

        summary = summariser.summarise_judgment(judgment)

        self.assertTrue(summary.issues)
        self.assertTrue(summary.held)
        self.assertTrue(summary.order)
        self.assertTrue(summary.summary)
        self.assertTrue(summary.flynote)
        self.assertTrue(summary.blurb)
