import json
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from peachjam.middleware import GeneralUpdateCacheMiddleware
from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings
from peachjam_search.models import SavedSearch, SearchHistory, SearchTrace
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

    def test_recent_searches_deduplicate_and_preserve_filters_and_mode(self):
        params = {"court": ["high-court"], "year": ["2025"], "is_most_recent": True}
        self.trace(filters=params, mode="hybrid", ordering="-date")
        newest = self.trace(filters=params, mode="hybrid", ordering="-date")
        self.trace(page=2)
        self.trace(kind=SearchTrace.Kind.PORTIONS)
        self.trace(search="timed out", status=SearchTrace.Status.TIMED_OUT)
        self.trace(field_searches={"title": "criminal law"})
        self.trace(search=" ")
        self.login()
        recent = self.shortcuts()["recent_searches"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["id"], str(newest.pk))
        self.assertEqual(
            parse_qs(urlparse(recent[0]["url"]).query),
            {
                "q": ["criminal law"],
                "court": ["high-court"],
                "year": ["2025"],
                "mode": ["hybrid"],
                "ordering": ["-date"],
                "page": ["1"],
            },
        )

    def test_recent_searches_load_without_extra_queries(self):
        self.trace(search="criminal law")
        self.trace(search="contract", filters={"date": ["2025-01-01", None]})
        with self.assertNumQueries(1):
            recent = OmniboxShortcuts().recent_searches(self.user)
        self.assertEqual(len(recent), 2)

    def update_history(
        self, action, url="/search/?q=Constitution", text="Constitution"
    ):
        return self.client.post(
            reverse("search_history"), {"action": action, "url": url, "text": text}
        )

    def test_history_removal_is_account_wide_and_preserves_analytics(self):
        self.trace(search="Constitution")
        self.trace(search="constitution", ordering="-score")
        self.login()
        response = self.update_history("remove")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recent_searches"], [])
        self.assertEqual(SearchTrace.objects.filter(user=self.user).count(), 2)
        other_browser = Client()
        other_browser.force_login(self.user)
        loaded = other_browser.get(self.url)
        self.assertEqual(
            json.loads(loaded.context["user_json"])["omnibox"]["recent_searches"], []
        )
        self.login(self.other)
        self.assertEqual(SearchHistory.objects.filter(user=self.other).count(), 0)
        self.assertEqual(self.update_history("record").status_code, 200)
        self.login()
        self.assertEqual(self.shortcuts()["recent_searches"], [])

    def test_repeating_removed_search_restores_it(self):
        self.login()
        self.update_history("remove")
        response = self.update_history(
            "record", "/search/?q=constitution&gsc.tab=0&ordering=-score&page=1"
        )
        self.assertEqual(len(response.json()["recent_searches"]), 1)
        self.assertFalse(SearchHistory.objects.get(user=self.user).removed)
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), 1)

    def test_history_requires_login_and_csrf(self):
        self.assertEqual(self.update_history("remove").status_code, 302)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(
            csrf_client.post(
                reverse("search_history"),
                {"action": "remove", "url": "/search/?q=law", "text": "law"},
            ).status_code,
            403,
        )

    def test_history_rejects_invalid_entries(self):
        self.login()
        for url in [
            "https://example.com/search/?q=law",
            "javascript:alert(1)",
            "/search/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.update_history("record", url).status_code, 400)
        self.assertEqual(SearchHistory.objects.count(), 0)

    def test_case_and_analytics_parameters_do_not_duplicate_history(self):
        self.trace(search="Constitution")
        self.trace(search="constitution", ordering="-score")
        self.login()
        self.assertEqual(len(self.shortcuts()["recent_searches"]), 1)
        self.update_history("record", "/search/?q=Constitution&gsc.tab=0")
        self.assertEqual(len(self.shortcuts()["recent_searches"]), 1)

    def test_distinct_filters_are_preserved(self):
        service = OmniboxShortcuts()
        self.assertEqual(
            service.search_key("/search/?q=law&court=b&court=a"),
            service.search_key("/fr/search/?court=a&court=b&q=LAW"),
        )
        self.assertNotEqual(
            service.search_key("/search/?q=law&court=a"),
            service.search_key("/search/?q=law&court=b"),
        )

    def test_history_preserves_original_query_when_deduplicating(self):
        self.login()
        url = "/search/?q=Foo+AND++Bar&court=high-court"
        self.update_history("record", url, "Foo AND  Bar")
        response = self.update_history(
            "record", "/search/?q=foo+and+bar&court=high-court&gsc.tab=0", "foo and bar"
        )
        self.assertEqual(len(response.json()["recent_searches"]), 1)
        self.assertEqual(SearchHistory.objects.filter(user=self.user).count(), 1)
        response = self.update_history("record", url, "Foo AND  Bar")
        params = parse_qs(urlparse(response.json()["recent_searches"][0]["url"]).query)
        self.assertEqual(params["q"], ["Foo AND  Bar"])

    def test_history_keeps_distinct_filters_sort_modes_and_pages(self):
        self.login()
        urls = [
            "/search/?q=law",
            "/search/?q=law&court=high-court",
            "/search/?q=law&ordering=-date",
            "/search/?q=law&mode=hybrid",
            "/search/?q=law&page=2",
        ]
        for url in urls:
            self.update_history("record", url, "law")
        response = self.update_history(
            "record", "/search/?q=LAW&page=1&ordering=-score&mode=text", "LAW"
        )
        self.assertEqual(len(response.json()["recent_searches"]), len(urls))
        self.assertEqual(
            SearchHistory.objects.filter(user=self.user).count(), len(urls)
        )

    def test_full_account_history_uses_one_bounded_query(self):
        service = OmniboxShortcuts()
        SearchHistory.objects.bulk_create(
            [
                SearchHistory(
                    user=self.user,
                    key=service.search_key(f"/search/?q=query-{i}"),
                    text=f"query-{i}",
                    query_string=f"q=query-{i}",
                )
                for i in range(30)
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            items = service.history(self.user)["recent_searches"]
        self.assertEqual(len(items), 12)
        self.assertEqual(len(queries), 1)
        self.assertIn("LIMIT 12", queries[0]["sql"])

    def test_trace_fallback_fills_history_past_removed_candidates(self):
        service = OmniboxShortcuts()
        for i in range(20):
            self.trace(search=f"query-{i}")
        SearchHistory.objects.bulk_create(
            [
                SearchHistory(
                    user=self.user,
                    key=service.search_key(f"/search/?q=query-{i}"),
                    text=f"query-{i}",
                    query_string=f"q=query-{i}",
                    removed=True,
                )
                for i in range(15, 20)
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            items = service.history(self.user)["recent_searches"]
        self.assertEqual(len(items), 12)
        self.assertEqual(items[0]["text"], "query-14")
        self.assertEqual(len(queries), 3)
        self.assertIn("LIMIT 12", queries[0]["sql"])
        self.assertIn("LIMIT 100", queries[1]["sql"])
        self.assertIn(" IN ", queries[2]["sql"])

    def test_locked_items_are_excluded(self):
        for item in (self.saved, self.folder, self.search):
            item.subscription_locked_at = timezone.now()
            item.save()
        self.login()
        self.assertEqual(self.shortcuts()["saved_items"], [])

    def test_recent_search_date_range_uses_search_page_parameters(self):
        self.trace(filters={"date": ["2025-01-01", "2025-12-31"]})
        self.login()
        recent = self.shortcuts()["recent_searches"]
        params = parse_qs(urlparse(recent[0]["url"]).query)
        self.assertEqual(params["date_from"], ["2025-01-01"])
        self.assertEqual(params["date_to"], ["2025-12-31"])
        self.assertNotIn("date", params)

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
