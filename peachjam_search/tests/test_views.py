from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from elasticsearch_dsl.response import Response


class SearchViewsTest(TestCase):
    fixtures = ["tests/countries", "tests/users"]

    def setUp(self):
        self.user = User.objects.get(username="admin@example.com")

    @patch("peachjam_search.engine.RetrieverSearch.execute")
    def test_explain(self, mock_search):
        mock_search.return_value = Response(
            mock_search,
            {
                "_shards": {
                    "failed": 0,
                },
                "hits": {
                    "total": {
                        "value": 0,
                    },
                    "hits": [],
                },
            },
        )

        response = self.client.get(reverse("search:search_explain") + "?search=test")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user)
        response = self.client.get(reverse("search:search_explain") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response.headers["Cache-Control"])

    @patch("peachjam_search.engine.RetrieverSearch.execute")
    def test_download(self, mock_search):
        mock_search.return_value = Response(
            mock_search,
            {
                "_shards": {
                    "failed": 0,
                },
                "hits": {
                    "total": {
                        "value": 0,
                    },
                    "hits": [],
                },
            },
        )

        response = self.client.get(reverse("search:search_download") + "?search=test")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user)
        response = self.client.get(reverse("search:search_download") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response.headers["Cache-Control"])

    @patch("peachjam_search.engine.RetrieverSearch.execute")
    def test_search(self, mock_search):
        mock_search.return_value = Response(
            mock_search,
            {
                "_shards": {
                    "failed": 0,
                },
                "hits": {
                    "total": {
                        "value": 0,
                    },
                    "hits": [],
                },
            },
        )

        response = self.client.get(reverse("search:search_documents") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("public", response.headers["Cache-Control"])
