import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from elasticsearch_dsl.response import Response

from peachjam.middleware import GeneralUpdateCacheMiddleware
from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings
from peachjam_search.models import SavedSearch, SearchTrace
from peachjam_search.omnibox import OmniboxShortcuts


class OmniboxTests(TestCase):
    fixtures = ["tests/countries", "tests/users", "documents/sample_documents"]

    def setUp(self):
        cache.clear()
        pjs = pj_settings()
        pjs.allow_save_documents = True
        pjs.allow_save_searches = True
        pjs.save()
        self.user = User.objects.get(username="officer@example.com")
        self.other = User.objects.create_user("other@example.com")
        self.user.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_folder", "view_savedsearch"])
        )
        self.saved = SavedDocument.objects.create(
            user=self.user, work=CoreDocument.objects.get(pk=5389).work
        )
        self.folder = Folder.objects.create(user=self.user, name="Research")
        self.search = SavedSearch.objects.create(
            user=self.user, q="criminal law", filters="court=high-court&year=2025"
        )
        self.url = reverse("loaded")

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def shortcuts(self):
        response = self.client.get(self.url)
        return json.loads(response.context["user_json"])["omnibox"]

    def trace(self, **kwargs):
        return SearchTrace.objects.create(
            **{
                "user": self.user,
                "search": "criminal law",
                "config_version": "test",
                "n_results": 2,
                "page": 1,
                "filters": None,
                **kwargs,
            }
        )

    def test_anonymous_response_is_empty_and_excluded_from_caching(self):
        self.trace()
        response = self.client.get(self.url)
        self.assertEqual(
            json.loads(response.context["user_json"])["omnibox"],
            {"user_id": None, "recent_searches": [], "saved_items": []},
        )
        middleware = GeneralUpdateCacheMiddleware(lambda request: response)
        self.assertFalse(
            middleware._should_update_cache(response.wsgi_request, response)
        )

    def test_shortcuts_belong_to_current_user_and_are_not_cached(self):
        self.trace()
        self.login()
        response = self.client.get(self.url)
        data = json.loads(response.context["user_json"])["omnibox"]
        self.assertEqual(data["user_id"], self.user.pk)
        self.assertEqual(
            {item["url"] for item in data["saved_items"]},
            {
                self.saved.get_absolute_url(),
                self.folder.get_absolute_url(),
                self.search.get_absolute_url(),
            },
        )
        self.assertEqual(len(data["recent_searches"]), 1)
        middleware = GeneralUpdateCacheMiddleware(lambda request: response)
        self.assertFalse(
            middleware._should_update_cache(response.wsgi_request, response)
        )
        self.login(self.other)
        data = self.shortcuts()
        self.assertEqual(data["saved_items"], [])
        self.assertEqual(data["recent_searches"], [])

    def test_language_prefixed_user_response_is_excluded_from_caching(self):
        from django.test import RequestFactory

        middleware = GeneralUpdateCacheMiddleware(lambda request: None)
        request = RequestFactory().get("/fr/user/loaded")
        self.assertFalse(middleware._should_update_cache(request, None))

    def test_history_uses_only_eligible_traces(self):
        excluded = [
            {"page": 2},
            {"kind": SearchTrace.Kind.PORTIONS},
            {"status": SearchTrace.Status.TIMED_OUT},
            {"field_searches": {"title": "law"}},
            {"filters": {"court": ["high-court"]}},
            {"filters": {"date": ["2025-01-01", None]}},
            {"search": " "},
            {"search": ""},
            {"hidden": True},
            {"mode": "hybrid"},
            {"ordering": "-date"},
        ]
        for kwargs in excluded:
            with self.subTest(kwargs=kwargs):
                trace = self.trace(**kwargs)
                self.assertFalse(
                    SearchTrace.objects.for_search_history()
                    .filter(pk=trace.pk)
                    .exists()
                )
        self.trace(search="Law", field_searches={}, filters={}, ordering="-score")
        newest = self.trace(search=" law ")
        self.login()
        items = self.shortcuts()["recent_searches"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], str(newest.pk))
        self.assertEqual(items[0]["text"], " law ")
        self.assertEqual(
            items[0]["delete_url"], reverse("search:history_delete", args=[newest.pk])
        )

    def test_recent_searches_use_one_query_and_latest_twelve_distinct_searches(self):
        for i in range(15):
            self.trace(search=f"query-{i}")
        for i in range(105):
            self.trace(search="repeated")
        with CaptureQueriesContext(connection) as queries:
            recent = OmniboxShortcuts().recent_searches(self.user)
        self.assertEqual(len(queries), 1)
        self.assertEqual(len(recent), 12)
        self.assertEqual(
            [x["text"] for x in recent[:3]], ["repeated", "query-14", "query-13"]
        )

    def remove_history(self, trace, client=None):
        return (client or self.client).post(
            reverse("search:history_delete", args=[trace.pk])
        )

    def test_history_removal_is_account_wide_and_preserves_analytics(self):
        first = self.trace(search="Constitution")
        second = self.trace(search=" constitution ", ordering="-score")
        other = self.trace(user=self.other, search="Constitution")
        filtered = self.trace(search="Constitution", filters={"court": ["high-court"]})
        advanced = self.trace(search="Constitution", field_searches={"title": "law"})
        self.login()
        response = self.remove_history(second)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recent_searches"], [])
        self.assertEqual(SearchTrace.objects.count(), 5)
        for trace in (first, second, other, filtered, advanced):
            trace.refresh_from_db()
            self.assertEqual(trace.hidden, trace in (first, second))
        other_browser = Client()
        other_browser.force_login(self.user)
        loaded = other_browser.get(self.url)
        self.assertEqual(
            json.loads(loaded.context["user_json"])["omnibox"]["recent_searches"], []
        )

    def test_repeating_removed_search_restores_it_with_a_new_trace(self):
        trace = self.trace()
        self.login()
        self.remove_history(trace)
        newest = self.trace()
        response = self.client.get(reverse("search:history"))
        self.assertEqual(
            [x["id"] for x in response.json()["recent_searches"]], [str(newest.pk)]
        )
        trace.refresh_from_db()
        self.assertTrue(trace.hidden)
        self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(
        CACHES={
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
        },
        CACHE_MIDDLEWARE_SECONDS=1800,
    )
    def test_cached_results_are_reused_with_fresh_private_traces(self):
        def results(search):
            return Response(
                search,
                {
                    "_shards": {"failed": 0},
                    "hits": {"total": {"value": 0}, "hits": []},
                    "aggregations": {},
                },
            )

        url = reverse("search:search_documents") + "?search=criminal+law"
        with patch(
            "peachjam_search.compiler.RetrieverSearch.execute",
            autospec=True,
            side_effect=results,
        ) as execute:
            first_anonymous = self.client.get(url)
            second_anonymous = self.client.get(url)
            for response in (first_anonymous, second_anonymous):
                self.assertEqual(response.status_code, 200)
                control = response.headers["Cache-Control"]
                self.assertIn("private", control)
                self.assertIn("no-store", control)
                self.assertIn("max-age=0", control)
                self.assertNotIn("public", control)
            self.assertNotEqual(
                first_anonymous.json()["trace_id"], second_anonymous.json()["trace_id"]
            )
            self.assertEqual(execute.call_count, 1)
            self.login()
            first_response = self.client.get(url)
            self.assertIn("no-store", first_response.headers["Cache-Control"])
            trace = SearchTrace.objects.get(pk=first_response.json()["trace_id"])
            self.assertEqual(trace.user, self.user)
            self.remove_history(trace)
            second_response = self.client.get(url)
            self.assertNotEqual(
                first_response.json()["trace_id"], second_response.json()["trace_id"]
            )
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(
                self.shortcuts()["recent_searches"][0]["id"],
                second_response.json()["trace_id"],
            )
            self.login(self.other)
            other_response = self.client.get(url)
            self.assertEqual(
                SearchTrace.objects.get(pk=other_response.json()["trace_id"]).user,
                self.other,
            )
            self.assertEqual(execute.call_count, 1)
            self.client.get(reverse("search:search_documents") + "?search=contract")
            self.assertEqual(execute.call_count, 2)

    def test_history_requires_login_and_csrf(self):
        trace = self.trace()
        self.assertEqual(self.remove_history(trace).status_code, 302)
        self.assertEqual(self.client.get(reverse("search:history")).status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(self.remove_history(trace, csrf_client).status_code, 403)

    def test_history_cannot_remove_another_users_trace_or_ineligible_trace(self):
        self.login()
        for trace in [
            self.trace(user=self.other),
            self.trace(filters={"court": ["high-court"]}),
            self.trace(hidden=True),
        ]:
            with self.subTest(trace=trace.pk):
                self.assertEqual(self.remove_history(trace).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse(
                    "search:history_delete",
                    args=["00000000-0000-0000-0000-000000000000"],
                )
            ).status_code,
            404,
        )
        trace = self.trace()
        self.assertEqual(
            self.client.get(
                reverse("search:history_delete", args=[trace.pk])
            ).status_code,
            405,
        )

    def test_locked_items_are_excluded(self):
        for item in (self.saved, self.folder, self.search):
            item.subscription_locked_at = timezone.now()
            item.save()
        self.login()
        self.assertEqual(self.shortcuts()["saved_items"], [])

    def test_disabled_saved_features_are_excluded(self):
        pjs = pj_settings()
        pjs.allow_save_documents = False
        pjs.allow_save_searches = False
        pjs.save()
        self.login()
        self.assertEqual(self.shortcuts()["saved_items"], [])

    def test_folder_and_saved_search_permissions_are_respected(self):
        self.user.user_permissions.clear()
        self.login()
        items = self.shortcuts()["saved_items"]
        self.assertEqual([item["type"] for item in items], ["document"])

    def test_advanced_saved_search_replays_original_criteria(self):
        self.search.q = None
        self.search.a = (
            '[{"text":"contract","fields":["title"],"condition":"","exact":true}]'
        )
        self.search.save()
        self.login()
        items = self.shortcuts()["saved_items"]
        item = next(item for item in items if item["type"] == "saved_search")
        self.assertEqual(item["url"], self.search.get_absolute_url())
        self.assertIn("contract", item["text"])

    def test_shortcut_titles_cannot_escape_the_user_script(self):
        self.folder.name = "</script><script>alert(1)</script>"
        self.folder.save()
        self.login()
        response = self.client.get(self.url)
        self.assertNotContains(response, self.folder.name)
        self.assertIn("JSON.parse(", response.content.decode())
        data = json.loads(response.context["user_json"])["omnibox"]
        self.assertIn(self.folder.name, [item["text"] for item in data["saved_items"]])

    def test_public_page_does_not_include_personal_shortcuts(self):
        self.login()
        response = self.client.get(reverse("home_page"))
        self.assertContains(response, 'data-component="SearchInput"')
        self.assertNotContains(response, "Research")


class SearchTraceURLTests(TestCase):
    def test_null_filters_and_ordering_do_not_break_replay(self):
        trace = SearchTrace(search="law", filters=None, page=1)
        params = parse_qs(urlparse(trace.get_search_url()).query)
        self.assertEqual(params, {"q": ["law"], "page": ["1"]})

    def test_dates_mode_and_repeated_filters_are_preserved(self):
        for date_range, expected_dates in [
            (
                ["2025-01-01", "2025-12-31"],
                {"date_from": ["2025-01-01"], "date_to": ["2025-12-31"]},
            ),
            (["2025-01-01", None], {"date_from": ["2025-01-01"]}),
            ([None, "2025-12-31"], {"date_to": ["2025-12-31"]}),
        ]:
            with self.subTest(date_range=date_range):
                trace = SearchTrace(
                    search="law",
                    page=2,
                    mode="hybrid",
                    ordering="-date",
                    filters={
                        "date": date_range,
                        "court": ["first", "second"],
                        "is_most_recent": True,
                    },
                )
                params = parse_qs(urlparse(trace.get_search_url()).query)
                self.assertEqual(
                    params,
                    {
                        "q": ["law"],
                        "page": ["2"],
                        "mode": ["hybrid"],
                        "ordering": ["-date"],
                        "court": ["first", "second"],
                        **expected_dates,
                    },
                )
