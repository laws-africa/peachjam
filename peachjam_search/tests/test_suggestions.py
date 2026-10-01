from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from elastic_transport import ConnectionError as ElasticsearchConnectionError
from elasticsearch_dsl.utils import AttrDict

from peachjam.models import Flynote, FlynoteDocumentCount
from peachjam_search.suggestions import (
    DocumentSuggestionProvider,
    FlynoteSuggestionProvider,
    SearchSuggestion,
    SearchSuggestionService,
)


class DocumentSuggestionProviderTest(TestCase):
    @patch("peachjam_search.suggestions.ElasticsearchSearchCompiler")
    def test_uses_document_nature_as_type_label(self, compiler_class):
        compiler_class.return_value.suggest.return_value = SimpleNamespace(
            suggest=SimpleNamespace(
                prefix=[
                    SimpleNamespace(
                        options=[
                            AttrDict(
                                {
                                    "_id": "42",
                                    "text": "Judicial Service Act",
                                    "_score": 4,
                                    "_source": {
                                        "nature": "Legislation",
                                        "expression_frbr_uri": "/akn/za/act/2020/1/eng@2020-01-01",
                                    },
                                }
                            )
                        ]
                    )
                ]
            )
        )

        suggestions = DocumentSuggestionProvider().suggest("jud")

        self.assertEqual("Judicial Service Act", suggestions[0].value)
        self.assertEqual("document", suggestions[0].type)
        self.assertEqual("Legislation", suggestions[0].type_label)
        self.assertIsNone(suggestions[0].target_id)
        compiler_class.return_value.suggest.assert_called_once_with("jud", size=5)

    @patch("peachjam_search.suggestions.ElasticsearchSearchCompiler")
    def test_returns_no_documents_when_elasticsearch_is_unavailable(
        self, compiler_class
    ):
        compiler_class.return_value.suggest.side_effect = ElasticsearchConnectionError(
            "unavailable"
        )

        provider = DocumentSuggestionProvider()
        self.assertEqual([], provider.suggest("jud"))
        self.assertTrue(provider.degraded)


class FlynoteSuggestionProviderTest(TestCase):
    def create_flynote(self, name, count, deprecated=False):
        flynote = Flynote.add_root(name=name, deprecated=deprecated)
        FlynoteDocumentCount.objects.create(flynote=flynote, count=count)
        return flynote

    @override_settings(
        PEACHJAM={**settings.PEACHJAM, "SUMMARISE_USE_FLYNOTE_TREE": True}
    )
    def test_returns_active_prefix_matches_with_documents(self):
        exact = self.create_flynote("Wrongful arrest", 2)
        popular = self.create_flynote("Wrongful arrest procedure", 20)
        self.create_flynote("Wrongful dismissal", 30)
        self.create_flynote("Wrongful arrest deprecated", 40, deprecated=True)
        self.create_flynote("Wrongful arrest unused", 0)

        suggestions = FlynoteSuggestionProvider().suggest("wrongful arrest")

        self.assertEqual(
            [exact.name, popular.name], [item.value for item in suggestions]
        )
        self.assertEqual(
            ["Legal topic", "Legal topic"], [item.type_label for item in suggestions]
        )

    def test_returns_nothing_when_flynote_tree_is_disabled(self):
        self.create_flynote("Wrongful arrest", 2)

        self.assertEqual([], FlynoteSuggestionProvider().suggest("wrongful"))


class SearchSuggestionServiceTest(TestCase):
    def test_validates_query_length(self):
        self.assertEqual([], SearchSuggestionService().suggest("ab"))
        self.assertEqual([], SearchSuggestionService().suggest("a" * 101))

    def test_balances_types_then_fills_unused_places(self):
        service = SearchSuggestionService()
        candidates = [
            SearchSuggestion(
                f"Document {number}", "document", "Document", source_rank=number
            )
            for number in range(6)
        ] + [SearchSuggestion("Supreme Court", "court", "Court")]

        selected = service.select_balanced(candidates)

        self.assertEqual("court", selected[3].type)
        self.assertEqual(7, len(selected))

    def test_deduplicates_suggestions_within_a_type(self):
        service = SearchSuggestionService()
        candidates = [
            SearchSuggestion("Supreme Court", "court", "Court"),
            SearchSuggestion("supreme court", "court", "Court"),
        ]

        self.assertEqual(1, len(service.select_balanced(candidates)))

    def test_exact_matches_rank_before_provider_prefix_matches(self):
        class DocumentProvider:
            def suggest(self, query):
                return [
                    SearchSuggestion("Supreme Court Act", "document", "Legislation")
                ]

        class CourtProvider:
            def suggest(self, query):
                return [SearchSuggestion("Sup", "court", "Court", match_rank=0)]

        service = SearchSuggestionService()
        service.providers = (DocumentProvider, CourtProvider)

        suggestions = service.suggest("sup")

        self.assertEqual("court", suggestions[0]["type"])

    def test_reports_when_a_provider_is_unavailable(self):
        class UnavailableProvider:
            degraded = True

            def suggest(self, query):
                return []

        service = SearchSuggestionService()
        service.providers = (UnavailableProvider,)

        self.assertEqual([], service.suggest("sup"))
        self.assertTrue(service.degraded)


@override_settings(
    PEACHJAM={**settings.PEACHJAM, "SEARCH_SUGGESTIONS": True},
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "search-suggestion-tests",
        }
    },
)
class SearchSuggestionViewTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("peachjam_search.views.search.SearchSuggestionService.suggest")
    def test_uses_server_cache_and_allows_short_client_cache(self, suggest):
        suggest.return_value = [
            {
                "value": "Supreme Court",
                "type": "court",
                "type_label": "Court",
            }
        ]
        url = reverse("search:search_documents").replace(
            "api/documents/", "api/documents/suggest/"
        )
        url += "?q=supreme"

        first = self.client.get(url)
        second = self.client.get(url)

        self.assertEqual(200, first.status_code)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(
            {
                "suggestions": [
                    {
                        "value": "Supreme Court",
                        "type": "court",
                        "type_label": "Court",
                    }
                ]
            },
            first.json(),
        )
        suggest.assert_called_once_with("supreme")
        self.assertIn("private", first.headers["Cache-Control"])
        self.assertNotIn("public", first.headers["Cache-Control"])
        self.assertIn("max-age=1800", first.headers["Cache-Control"])
        self.assertIn("Accept-Language", first.headers["Vary"])

    @patch("peachjam_search.views.search.SearchSuggestionService.suggest")
    def test_changing_flynote_setting_uses_a_fresh_server_cache_entry(self, suggest):
        suggest.side_effect = [
            [{"value": "Wrongful arrest", "type": "flynote"}],
            [{"value": "Wrongful arrest", "type": "document"}],
        ]
        url = (
            reverse("search:search_documents").replace(
                "api/documents/", "api/documents/suggest/"
            )
            + "?q=wrongful"
        )
        base_settings = settings.PEACHJAM

        with override_settings(
            PEACHJAM={**base_settings, "SUMMARISE_USE_FLYNOTE_TREE": True}
        ):
            enabled = self.client.get(url)
        with override_settings(
            PEACHJAM={**base_settings, "SUMMARISE_USE_FLYNOTE_TREE": False}
        ):
            disabled = self.client.get(url)

        self.assertEqual("flynote", enabled.json()["suggestions"][0]["type"])
        self.assertEqual("document", disabled.json()["suggestions"][0]["type"])
        self.assertEqual(2, suggest.call_count)

    @patch("peachjam_search.views.search.SearchSuggestionService")
    def test_degraded_suggestions_have_a_short_cache_lifetime(self, service_class):
        service = service_class.return_value
        service.suggest.return_value = [{"value": "Supreme Court", "type": "court"}]
        service.degraded = True
        url = reverse("search:search_documents").replace(
            "api/documents/", "api/documents/suggest/"
        )

        with patch(
            "peachjam_search.views.search.cache.set", wraps=cache.set
        ) as set_cache:
            response = self.client.get(url + "?q=supreme")

        self.assertEqual(200, response.status_code)
        self.assertEqual(30, set_cache.call_args.args[2])
        self.assertIn("max-age=30", response.headers["Cache-Control"])
