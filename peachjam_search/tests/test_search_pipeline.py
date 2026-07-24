from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from peachjam_search.profiles import SearchProfileSet, get_default_search_profile_set
from peachjam_search.search_pipeline import (
    PageRankSettings,
    QueryAnalyser,
    QueryAnalysis,
    SearchPlanner,
    SearchQuery,
)


class FakeClassifier:
    def classify(self, query):
        return type(
            "Classification",
            (),
            {
                "query_clean": query.strip(),
                "label": type("Label", (), {"value": "case_name"})(),
                "confidence": 0.9,
            },
        )()


class SearchPipelineTest(SimpleTestCase):
    def setUp(self):
        packaged_profile_set = get_default_search_profile_set()
        self.profile_set = SearchProfileSet(
            default=packaged_profile_set.default,
            labels={
                "case_name": replace(
                    packaged_profile_set.default,
                    name="case_name",
                )
            },
        )
        self.planner = SearchPlanner(
            self.profile_set,
            pagerank_settings=PageRankSettings(5, 10),
        )

    def request(self, **overrides):
        data = {
            "query": "Example v State",
            "field_queries": {},
            "mode": "text",
            "filters": {},
            "facets": [],
            "page": 1,
            "page_size": 10,
            "ordering": "-score",
            "explain": False,
        }
        data.update(overrides)
        return SearchQuery(**data)

    def test_analyser_adapts_query_classifier(self):
        analysis = QueryAnalyser(classifier=FakeClassifier()).analyse(
            " Example v State "
        )

        self.assertEqual("Example v State", analysis.clean_query)
        self.assertEqual("case_name", analysis.intent)
        self.assertEqual(0.9, analysis.confidence)

    def test_planner_uses_label_profile_and_legacy_text_clauses(self):
        analysis = QueryAnalysis(
            raw_query="Example v State", intent="case_name", confidence=0.9
        )

        plan = self.planner.build(self.request(), analysis)

        self.assertEqual("case_name", plan.profile.name)
        self.assertEqual(
            ["basic", "content_phrase", "nested_pages", "nested_provisions"],
            [clause.name for clause in plan.retrieval_clauses],
        )
        self.assertEqual(["pagerank"], [signal.name for signal in plan.ranking_signals])
        self.assertEqual(5, plan.ranking_signals[0].boost)
        self.assertEqual(10, plan.ranking_signals[0].saturation_pivot)

    def test_manual_advanced_search_uses_default_profile_without_analysis(self):
        request = self.request(field_queries={"case_name": "Example v State"})
        analysis = QueryAnalysis(raw_query="", clean_query="")

        plan = self.planner.build(request, analysis)

        self.assertEqual("default", plan.profile.name)
        self.assertEqual(
            ["advanced_per_field", "advanced_all", "advanced_content"],
            [clause.name for clause in plan.retrieval_clauses],
        )

    def test_semantic_plan_has_no_text_or_pagerank_clauses(self):
        analysis = QueryAnalysis(
            raw_query="Example v State", intent="case_name", confidence=0.9
        )

        plan = self.planner.build(self.request(mode="semantic"), analysis)

        self.assertEqual((), plan.retrieval_clauses)
        self.assertEqual((), plan.ranking_signals)

    def test_unknown_label_uses_default_profile(self):
        analysis = QueryAnalysis(
            raw_query="Example v State", intent="unknown", confidence=0.9
        )

        plan = self.planner.build(self.request(), analysis)

        self.assertEqual("default", plan.profile.name)

    @patch("peachjam_search.search_pipeline.pj_settings")
    def test_planner_reads_production_pagerank_settings_into_the_plan(
        self, mock_pj_settings
    ):
        mock_pj_settings.return_value = SimpleNamespace(
            pagerank_boost_value=7,
            pagerank_pivot_value=0.25,
        )
        planner = SearchPlanner(self.profile_set)

        plan = planner.build(self.request(), QueryAnalysis(raw_query="Example v State"))

        signal = plan.ranking_signals[0]
        self.assertEqual(7, signal.boost)
        self.assertEqual(0.25, signal.saturation_pivot)
        mock_pj_settings.assert_called_once_with()
