import datetime
from types import SimpleNamespace

from countries_plus.models import Country
from django.conf import settings
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from languages_plus.models import Language

from peachjam.models import Court, Judgment
from peachjam.models.flynote import Flynote, FlynoteDocumentCount, JudgmentFlynote
from peachjam_search.flynotes import FlynoteSearchMatcher
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

        self.assertEqual([direct, supported], [match.flynote for match in matches])
        self.assertEqual(
            ["direct_query", "document_support"], [match.source for match in matches]
        )
        self.assertEqual(["Criminal law", "Wrongful arrest"], matches[0].path_labels)
        html = render_to_string(
            "peachjam_search/_flynote_search_hit_list.html",
            {"flynote_hits": matches},
        )
        self.assertIn("Explore legal topics related to your search", html)
        self.assertIn("Wrongful arrest", html)
        self.assertIn('data-flynote-source="direct_query"', html)

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

    def test_requires_two_results_to_support_a_fallback_topic(self):
        supported = self.create_topic("Criminal law", "Property offences", 10)
        judgment = self.make_judgment("Only supporting result")
        JudgmentFlynote.objects.create(document=judgment, flynote=supported)

        matches = FlynoteSearchMatcher().match(
            "property damage",
            [SimpleNamespace(id=judgment.pk, position=1, document=judgment)],
        )

        self.assertEqual([], matches)

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

        self.assertEqual([child], [match.flynote for match in matches])

    def test_excludes_topics_with_only_one_linked_judgment(self):
        self.create_topic("Criminal law", "Wrongful arrest", 1)

        matches = FlynoteSearchMatcher().match("wrongful arrest", [])

        self.assertEqual([], matches)

    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SUMMARISE_USE_FLYNOTE_TREE": True,
            "SHOW_FLYNOTE_TOPICS": True,
        }
    )
    def test_view_only_shows_topics_for_first_page_legal_term_searches(self):
        topic = self.create_topic("Criminal law", "Wrongful arrest", 10)
        view = DocumentSearchView()
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
        self.assertEqual([], view.match_flynotes(engine, []))
