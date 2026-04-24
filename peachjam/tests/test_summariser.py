import os
import unittest
from unittest.mock import MagicMock

from django.test import TransactionTestCase as TestCase
from django.utils.text import slugify

from peachjam.analysis.summariser import JudgmentSummariser, JudgmentSummary
from peachjam.models import Flynote, FlynoteDocumentCount

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
class JudgmentSummariserMatchFlynotesE2ETest(TestCase):
    maxDiff = None

    def setUp(self):
        for root in ROOTS.strip().splitlines():
            root = root.strip()
            Flynote.add_root(name=root, slug=slugify(root))

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
            slug="civil-procedure-post-judgment-interest",
        )
        FlynoteDocumentCount.objects.create(
            flynote=self.post_judgment_interest,
            count=320,
        )
        # The AI should normalize "Post judgment interest" to this database entry for component 2.
        self.unrelated_child = self.post_judgment_interest.add_child(
            name="Taxation of costs",
            slug="civil-procedure-post-judgment-interest-taxation-of-costs",
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
