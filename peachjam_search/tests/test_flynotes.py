import datetime
from dataclasses import replace
from types import SimpleNamespace

from countries_plus.models import Country
from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from languages_plus.models import Language

from peachjam.models import Court, Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote
from peachjam_search.flynotes import FlynoteSearchMatcher
from peachjam_search.models import SearchFlynoteResult, SearchTrace
from peachjam_search.search_pipeline import QueryAnalysis, SearchQuery
from peachjam_search.views.search import DocumentSearchView


class FlynoteSearchMatcherTest(TestCase):
    fixtures = ["tests/countries", "tests/courts", "tests/languages"]

    def make_judgment(self, case_name):
        return Judgment.objects.create(
            case_name=case_name,
            jurisdiction=Country.objects.first(),
            court=Court.objects.first(),
            date=datetime.date(2025, 1, 1),
            language=Language.objects.first(),
        )

    def create_topic(self, root_name, name, count):
        root = Flynote.add_root(name=root_name)
        flynote = root.add_child(name=name)
        FlynoteDocumentCount.objects.create(flynote=root, count=count)
        FlynoteDocumentCount.objects.create(flynote=flynote, count=count)
        return flynote

    def test_prefers_direct_matches_and_fills_remaining_cards(self):
        direct = self.create_topic("Criminal law", "Wrongful arrest", 10)
        supported = self.create_topic("Criminal procedure", "Arrest procedure", 4)
        first_judgment = self.make_judgment("First supported result")
        second_judgment = self.make_judgment("Second supported result")
        JudgmentFlynote.objects.bulk_create(
            [
                JudgmentFlynote(document=first_judgment, flynote=supported),
                JudgmentFlynote(document=second_judgment, flynote=supported),
            ]
        )

        matches = FlynoteSearchMatcher().match(
            "wrongful arrest",
            [
                SimpleNamespace(
                    id=first_judgment.pk, position=1, document=first_judgment
                ),
                SimpleNamespace(
                    id=second_judgment.pk, position=2, document=second_judgment
                ),
            ],
        )

        trace = SearchTrace.objects.create(
            config_version="test", search="wrongful arrest", n_results=2, page=1
        )
        matches = DocumentSearchView().save_flynote_results(trace, matches)

        self.assertEqual([direct, supported], [match.flynote for match in matches])
        self.assertEqual(
            ["direct_query", "document_support"], [match.source for match in matches]
        )
        self.assertEqual(["Criminal law", "Wrongful arrest"], matches[0].path_labels)
        html = render_to_string(
            "peachjam_search/_flynote_search_hit_list.html",
            {
                "flynote_hits": matches,
                "flynote_search_url": "/topics/?q=wrongful+arrest",
            },
        )
        self.assertIn("Explore legal topics related to your search", html)
        self.assertIn("Wrongful arrest", html)
        self.assertIn('data-flynote-source="direct_query"', html)
        self.assertIn('data-key-link-feature="topics"', html)
        self.assertIn('data-key-link="topic"', html)
        self.assertIn(f'data-flynote-result-id="{matches[0].result_id}"', html)
        self.assertIn('class="badge rounded-pill bg-secondary text-nowrap"', html)
        self.assertIn(">10</span>", html)
        self.assertIn('href="/topics/?q=wrongful+arrest"', html)
        self.assertIn("Explore all related legal topics", html)
        self.assertNotIn("Explore topic", html)

    def test_uses_ranked_judgment_topics_when_there_is_no_direct_match(self):
        first = self.create_topic("Criminal law", "Property offences", 10)
        second = self.create_topic("Civil law", "Damages", 4)
        first_judgments = [
            self.make_judgment("First result"),
            self.make_judgment("First result support"),
        ]
        second_judgments = [
            self.make_judgment("Second result"),
            self.make_judgment("Second result support"),
        ]
        JudgmentFlynote.objects.bulk_create(
            [
                *(
                    JudgmentFlynote(document=judgment, flynote=first)
                    for judgment in first_judgments
                ),
                *(
                    JudgmentFlynote(document=judgment, flynote=second)
                    for judgment in second_judgments
                ),
            ]
        )

        matches = FlynoteSearchMatcher().match(
            "damages for property",
            [
                SimpleNamespace(
                    id=first_judgments[0].pk,
                    position=1,
                    document=first_judgments[0],
                ),
                SimpleNamespace(
                    id=second_judgments[0].pk,
                    position=2,
                    document=second_judgments[0],
                ),
                SimpleNamespace(
                    id=first_judgments[1].pk,
                    position=3,
                    document=first_judgments[1],
                ),
                SimpleNamespace(
                    id=second_judgments[1].pk,
                    position=4,
                    document=second_judgments[1],
                ),
            ],
        )

        self.assertEqual([first, second], [match.flynote for match in matches])
        self.assertTrue(all(match.source == "document_support" for match in matches))
        self.assertEqual(
            ["lexical_document_support", "lexical_document_support"],
            [match.selection_reason for match in matches],
        )

    def test_requires_two_results_to_support_a_fallback_topic(self):
        supported = self.create_topic("Criminal law", "Property offences", 10)
        judgment = self.make_judgment("Only supporting result")
        JudgmentFlynote.objects.create(document=judgment, flynote=supported)

        matches = FlynoteSearchMatcher().match(
            "property damage",
            [SimpleNamespace(id=judgment.pk, position=1, document=judgment)],
        )

        self.assertEqual([], matches)

    def test_uses_strong_convergence_without_query_word_overlap(self):
        arson = self.create_topic("Criminal law", "Arson", 10)
        judgments = [
            self.make_judgment("First result"),
            self.make_judgment("Third result"),
            self.make_judgment("Fifth result"),
        ]
        JudgmentFlynote.objects.bulk_create(
            [
                JudgmentFlynote(document=judgment, flynote=arson)
                for judgment in judgments
            ]
        )

        matches = FlynoteSearchMatcher().match(
            "setting fire to crops",
            [
                SimpleNamespace(id=judgments[0].pk, position=1, document=judgments[0]),
                SimpleNamespace(id=judgments[1].pk, position=3, document=judgments[1]),
                SimpleNamespace(id=judgments[2].pk, position=5, document=judgments[2]),
            ],
        )

        self.assertEqual([arson], [match.flynote for match in matches])
        self.assertEqual(["document_support"], [match.source for match in matches])
        self.assertEqual(
            ["strong_document_convergence"],
            [match.selection_reason for match in matches],
        )
        html = render_to_string(
            "peachjam_search/_flynote_search_hit_list.html",
            {"flynote_hits": matches, "flynote_search_url": None},
        )
        self.assertNotIn("Explore all related legal topics", html)

    def test_records_flynote_result_display_metadata(self):
        direct = self.create_topic("Criminal law", "Wrongful arrest", 10)
        trace = SearchTrace.objects.create(
            config_version="test", search="wrongful arrest", n_results=1, page=1
        )
        hit = FlynoteSearchMatcher().match("wrongful arrest", [])[0]

        tracked_hit = DocumentSearchView().save_flynote_results(trace, [hit])[0]

        result = SearchFlynoteResult.objects.get(pk=tracked_hit.result_id)
        self.assertEqual(trace, result.search_trace)
        self.assertEqual(direct, result.flynote)
        self.assertEqual("Wrongful arrest", result.flynote_name)
        self.assertEqual(
            ["Criminal law", "Wrongful arrest"], result.flynote_path_labels
        )
        self.assertEqual(1, result.position)
        self.assertEqual("document_search_card", result.surface)
        self.assertEqual("direct_query", result.source)
        self.assertEqual("direct_name_match", result.selection_reason)

    def test_deduplicates_topics_with_the_same_name(self):
        most_popular = self.create_topic("Criminal law", "Rape", 10)
        self.create_topic("Criminal procedure", "rape", 5)

        matches = FlynoteSearchMatcher().match("rape", [])

        self.assertEqual([most_popular], [match.flynote for match in matches])

    def test_does_not_show_ancestor_and_descendant_cards_together(self):
        root = Flynote.add_root(name="Criminal law")
        parent = root.add_child(name="Arrest")
        child = parent.add_child(name="Wrongful arrest")
        FlynoteDocumentCount.objects.bulk_create(
            [
                FlynoteDocumentCount(flynote=root, count=5),
                FlynoteDocumentCount(flynote=parent, count=5),
                FlynoteDocumentCount(flynote=child, count=5),
            ]
        )

        matches = FlynoteSearchMatcher().match("arrest", [])

        self.assertEqual([parent], [match.flynote for match in matches])

    def test_excludes_partial_matches_with_only_one_linked_judgment(self):
        self.create_topic("Criminal law", "Wrongful arrest", 1)

        matches = FlynoteSearchMatcher().match("wrongful", [])

        self.assertEqual([], matches)

    def test_exact_topic_is_resolved_even_with_one_linked_judgment(self):
        topic = self.create_topic("Criminal law", "Wrongful arrest", 1)

        matches = FlynoteSearchMatcher().match("Wrongful arrest", [])

        self.assertEqual([topic], [match.flynote for match in matches])
        self.assertEqual("direct_name_match", matches[0].selection_reason)

    def test_exact_topic_takes_priority_over_popular_descendants(self):
        topic = self.create_topic("Criminal law", "Wrongful arrest", 1)
        child = topic.add_child(name="Wrongful arrest procedure")
        FlynoteDocumentCount.objects.create(flynote=child, count=20)

        matches = FlynoteSearchMatcher().match("wrongful arrest", [])

        self.assertEqual([topic], [match.flynote for match in matches])

    def test_exact_only_matching_excludes_partial_and_inferred_topics(self):
        topic = self.create_topic("Criminal law", "Arrest procedure", 4)
        judgments = [self.make_judgment(f"Case {number}") for number in range(2)]
        JudgmentFlynote.objects.bulk_create(
            [
                JudgmentFlynote(document=judgment, flynote=topic)
                for judgment in judgments
            ]
        )
        hits = [
            SimpleNamespace(id=judgment.pk, position=position, document=judgment)
            for position, judgment in enumerate(judgments, start=1)
        ]

        matcher = FlynoteSearchMatcher()
        self.assertEqual(
            [topic], [hit.flynote for hit in matcher.match("arrest", hits)]
        )
        self.assertEqual([], matcher.match("arrest", hits, exact_only=True))

    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SUMMARISE_USE_FLYNOTE_TREE": True,
            "SHOW_FLYNOTE_TOPICS": True,
        }
    )
    def test_view_matches_topic_names_independently_of_intent_or_suggestion(self):
        topic = self.create_topic("Criminal law", "Wrongful arrest", 10)
        view = DocumentSearchView()
        view.request = RequestFactory().get("/search/")
        engine = SimpleNamespace(
            search_query=SearchQuery(
                query="wrongful arrest",
                field_queries={},
                mode="text",
                filters={},
                facets=[],
                page=1,
                page_size=10,
                ordering="-score",
                explain=False,
            ),
            analysis=QueryAnalysis(raw_query="wrongful arrest", intent="legal_term"),
        )

        matches = view.match_flynotes(engine, [])

        self.assertEqual([topic], [match.flynote for match in matches])
        engine.analysis = QueryAnalysis(raw_query="wrongful arrest", intent="case_name")
        self.assertEqual(matches, view.match_flynotes(engine, []))

        # Suggestion metadata must not bypass intent checks for partial matches.
        exact_query = engine.search_query
        engine.search_query = replace(exact_query, query="wrongful")
        self.assertEqual([], view.match_flynotes(engine, []))
        engine.analysis = QueryAnalysis(raw_query="wrongful", intent="legal_term")
        self.assertEqual(matches, view.match_flynotes(engine, []))
        engine.search_query = exact_query

        view.request = RequestFactory().get("/search/", {"suggestion": "flynote"})
        self.assertEqual(matches, view.match_flynotes(engine, []))

        # Even a stale or incorrect suggestion ID cannot change the cards.
        view.request = RequestFactory().get(
            "/search/", {"suggestion": "flynote", "suggestion_id": "999999"}
        )
        self.assertEqual(matches, view.match_flynotes(engine, []))

        for overrides in ({"page": 2}, {"field_queries": {"title": "arrest"}}):
            with self.subTest(overrides=overrides):
                query = engine.search_query
                engine.search_query = replace(query, **overrides)
                self.assertEqual([], view.match_flynotes(engine, []))
                engine.search_query = query

        with self.settings(
            PEACHJAM={
                **settings.PEACHJAM,
                "SUMMARISE_USE_FLYNOTE_TREE": False,
                "SHOW_FLYNOTE_TOPICS": False,
            }
        ):
            self.assertEqual([], view.match_flynotes(engine, []))
        with self.settings(
            PEACHJAM={
                **settings.PEACHJAM,
                "SUMMARISE_USE_FLYNOTE_TREE": True,
                "SHOW_FLYNOTE_TOPICS": False,
            }
        ):
            self.assertEqual([], view.match_flynotes(engine, []))
