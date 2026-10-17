from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from peachjam.models import CoreDocument, Folder, SavedDocument, pj_settings
from peachjam_search.models import SavedSearch, SearchTrace


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
        self.url = reverse("search:omnibox_shortcuts")

    def login(self, user=None):
        self.client.force_login(user or self.user)

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

    def test_anonymous_response_is_empty_and_private(self):
        self.trace()
        response = self.client.get(self.url)
        self.assertEqual(
            response.json(),
            {"user_id": None, "recent_searches": [], "saved_items": []},
        )
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Cookie", response["Vary"])

    def test_shortcuts_belong_to_current_user_and_are_not_cached(self):
        self.trace()
        self.login()
        response = self.client.get(self.url)
        data = response.json()
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
        self.assertIn("no-store", response["Cache-Control"])
        self.login(self.other)
        data = self.client.get(self.url).json()
        self.assertEqual(data["saved_items"], [])
        self.assertEqual(data["recent_searches"], [])

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
        recent = self.client.get(self.url).json()["recent_searches"]
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

    def test_locked_items_are_excluded(self):
        for item in (self.saved, self.folder, self.search):
            item.subscription_locked_at = timezone.now()
            item.save()
        self.login()
        self.assertEqual(self.client.get(self.url).json()["saved_items"], [])

    def test_recent_search_date_range_uses_search_page_parameters(self):
        self.trace(filters={"date": ["2025-01-01", "2025-12-31"]})
        self.login()
        recent = self.client.get(self.url).json()["recent_searches"]
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
        self.assertEqual(self.client.get(self.url).json()["saved_items"], [])

    def test_folder_and_saved_search_permissions_are_respected(self):
        self.user.user_permissions.clear()
        self.login()
        items = self.client.get(self.url).json()["saved_items"]
        self.assertEqual([item["type"] for item in items], ["document"])

    def test_advanced_saved_search_replays_original_criteria(self):
        self.search.q = None
        self.search.a = (
            '[{"text":"contract","fields":["title"],"condition":"","exact":true}]'
        )
        self.search.save()
        self.login()
        items = self.client.get(self.url).json()["saved_items"]
        item = next(item for item in items if item["type"] == "saved_search")
        self.assertEqual(item["url"], self.search.get_absolute_url())
        self.assertIn("contract", item["text"])

    def test_prototype_page_contains_no_personalised_data(self):
        self.login()
        response = self.client.get(reverse("search:search_box"))
        self.assertContains(response, 'data-component="SearchInput"')
        self.assertContains(response, 'id="main-page-heading"')
        self.assertNotContains(response, "criminal law")
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
