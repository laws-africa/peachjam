from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from elasticsearch_dsl.response import Response

from peachjam.models import CoreDocument
from peachjam_search.models import SearchTrace


class SearchViewsTest(TestCase):
    fixtures = ["tests/countries", "tests/users", "documents/sample_documents"]

    def setUp(self):
        self.user = User.objects.get(username="officer@example.com")
        # ensure user has the correct permission
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="can_download_search",
                content_type=ContentType.objects.get_for_model(SearchTrace),
            ),
            Permission.objects.get(
                codename="can_debug_search",
                content_type=ContentType.objects.get_for_model(SearchTrace),
            ),
        )

    @patch("peachjam_search.engine.RetrieverSearch.execute", autospec=True)
    def test_explain(self, mock_search):
        doc = CoreDocument.objects.first()

        def resp(search):
            return Response(
                search,
                {
                    "_shards": {
                        "failed": 0,
                    },
                    "hits": {
                        "total": {
                            "value": 1,
                        },
                        "hits": [
                            {
                                "_id": str(doc.pk),
                                "_index": search.index,
                                "_score": 10.0,
                                "_source": {
                                    "expression_frbr_uri": doc.expression_frbr_uri,
                                },
                            }
                        ],
                    },
                },
            )

        mock_search.side_effect = resp

        response = self.client.get(reverse("search:search_explain") + "?search=test")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user)
        response = self.client.get(reverse("search:search_explain") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response.headers["Cache-Control"])

    @patch("peachjam_search.engine.RetrieverSearch.execute", autospec=True)
    def test_download(self, mock_search):
        doc = CoreDocument.objects.first()
        # this tests escaping dodgy chars in xlsx
        doc.title = "Title with \x02 dodgy char"
        doc.save()

        def resp(search):
            return Response(
                search,
                {
                    "_shards": {
                        "failed": 0,
                    },
                    "hits": {
                        "total": {
                            "value": 1,
                        },
                        "hits": [
                            {
                                "_id": str(doc.pk),
                            }
                        ],
                    },
                },
            )

        mock_search.side_effect = resp

        response = self.client.get(reverse("search:search_download") + "?search=test")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.user)
        response = self.client.get(reverse("search:search_download") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.headers["Content-Type"],
        )
        self.assertIn("no-cache", response.headers["Cache-Control"])

    @patch("peachjam_search.engine.RetrieverSearch.execute", autospec=True)
    def test_search(self, mock_search):
        doc = CoreDocument.objects.first()

        def resp(search):
            return Response(
                search,
                {
                    "_shards": {
                        "failed": 0,
                    },
                    "hits": {
                        "total": {
                            "value": 0,
                        },
                        "hits": [
                            {
                                "_id": str(doc.pk),
                                "_index": search.index,
                                "_score": 10.0,
                                "_source": {
                                    "expression_frbr_uri": doc.expression_frbr_uri,
                                },
                            }
                        ],
                    },
                },
            )

        mock_search.side_effect = resp

        response = self.client.get(reverse("search:search_documents") + "?search=test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=900", response.headers["Cache-Control"])
