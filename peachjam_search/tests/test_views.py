from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response

from peachjam.models import CoreDocument, Label
from peachjam_search.entity_matcher import EntitySearchHit
from peachjam_search.models import SearchTrace
from peachjam_search.views.api import PortionSearchView
from peachjam_search.views.search import DocumentSearchView


class SearchViewsTest(TestCase):
    fixtures = ["tests/countries", "tests/users", "documents/sample_documents"]

    def setUp(self):
        cache.clear()
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

    @override_settings(
        PEACHJAM={
            **settings.PEACHJAM,
            "SEARCH_SEMANTIC": True,
        }
    )
    @patch("peachjam_search.engine.SearchEngine.get_query_embedding")
    @patch("peachjam_search.engine.RetrieverSearch.execute", autospec=True)
    def test_hybrid_download_expands_retriever_window(
        self, mock_search, mock_get_query_embedding
    ):
        doc = CoreDocument.objects.first()
        mock_get_query_embedding.return_value = [0.1, 0.2]

        def resp(search):
            query = search.to_dict()
            self.assertEqual(
                1000,
                query["retriever"]["rrf"]["rank_window_size"],
            )
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

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("search:search_download") + "?search=test&mode=hybrid"
        )
        self.assertEqual(response.status_code, 200)

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

    @patch("peachjam_search.engine.RetrieverSearch.execute", autospec=True)
    def test_search_includes_entity_hits_above_document_hits(self, mock_search):
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

        response = self.client.get(
            reverse("search:search_documents")
            + "?search=ECOWAS%20Community%20Court%20of%20Justice"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ECOWAS Community Court of Justice", data["entity_results_html"])
        self.assertIn("Court", data["entity_results_html"])
        self.assertNotIn("ECOWAS Community Court of Justice", data["results_html"])
        self.assertIn(doc.title, data["results_html"])

    def test_entity_hit_does_not_use_document_click_tracking_attributes(self):
        request = RequestFactory().get("/search/?search=test")
        entity_hit = EntitySearchHit(
            entity_type="court",
            type_label="Court",
            entity_id=1,
            label="ECOWAS Community Court of Justice",
            url="/court/ecowascj/",
            match_type="exact",
            confidence=1.0,
        )

        html = render_to_string(
            "peachjam_search/_entity_search_hit.html",
            {
                "request": request,
                "entity_hit": entity_hit,
            },
            request=request,
        )

        self.assertIn("ECOWAS Community Court of Justice", html)
        self.assertNotIn("data-position", html)
        self.assertNotIn("data-frbr-uri", html)

    def test_search_trace_strips_null_bytes_before_saving(self):
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(id=uuid4())

        request = RequestFactory().get(
            reverse("search:search_documents"),
            {
                "search": "nul\x00search",
                "suggestion": "prefix\x00selected",
            },
            HTTP_USER_AGENT="agent-browser",
        )
        request.user = self.user
        request.id = "none"

        view = DocumentSearchView()
        view.request = request
        engine = SimpleNamespace(field_queries={}, filters={}, mode="text", page=1)

        with patch(
            "peachjam_search.views.search.SearchTrace.objects.create",
            side_effect=create,
        ) as mock_create:
            trace = view.save_search_trace(engine, 1)

        self.assertIsNotNone(trace)
        mock_create.assert_called_once()
        self.assertEqual("nul search", captured["search"])
        self.assertEqual({}, captured["field_searches"])
        self.assertEqual({}, captured["filters"])
        self.assertEqual("prefix selected", captured["suggestion"])
        self.assertEqual("agent-browser", captured["user_agent"])
        self.assertEqual("nul search", captured["query_clean"])
        self.assertNotIn("\x00", captured["filters_string"])

    def test_search_hit_links_open_in_same_tab(self):
        request = RequestFactory().get("/search/?search=test")
        doc = CoreDocument.objects.first()
        hit = {
            "document": doc,
            "position": 1,
            "best_match": False,
            "highlight": {},
            "pages": [
                {
                    "page_num": 3,
                    "highlight": {"pages_body": ["example"]},
                }
            ],
            "provisions": [
                {
                    "id": "sec_1",
                    "title": "Section 1",
                    "highlight": {"provisions_body": ["example"]},
                    "parents": [],
                }
            ],
        }

        html = render_to_string(
            "peachjam_search/_search_hit.html",
            {
                "request": request,
                "hit": hit,
                "show_jurisdiction": False,
                "can_debug": False,
            },
            request=request,
        )

        self.assertNotIn(
            f'target="_blank"\n           href="{doc.get_absolute_url}"',
            html,
        )
        self.assertNotIn(f'target="_blank">{doc.get_absolute_url}#page-3', html)
        self.assertNotIn(f'target="_blank">{doc.get_absolute_url}#sec_1', html)

    def test_search_hit_includes_document_labels(self):
        request = RequestFactory().get("/search/?search=test")
        doc = CoreDocument.objects.first()
        doc.labels.add(
            Label.objects.create(name="Reported", code="reported", level="success")
        )
        hit = {
            "document": doc,
            "position": 1,
            "best_match": False,
            "highlight": {},
            "pages": [],
            "provisions": [],
        }

        html = render_to_string(
            "peachjam_search/_search_hit.html",
            {
                "request": request,
                "hit": hit,
                "show_jurisdiction": False,
                "can_debug": False,
            },
            request=request,
        )

        self.assertIn("Reported", html)
        self.assertIn("badge rounded-pill bg-success", html)

    def test_search_hit_flynote_preserves_line_breaks(self):
        request = RequestFactory().get("/search/?search=test")
        doc = SimpleNamespace(
            id=1,
            title="Example judgment",
            citation=None,
            alternative_names=None,
            locality=None,
            date="2024-01-01",
            court="High Court",
            author_list=None,
            matter_type=None,
            doc_type="judgment",
            blurb=None,
            flynote="Line one\nLine two",
            flynote_lines=["Line one", "Line two"],
            get_absolute_url=lambda: "/akn/example",
            expression_frbr_uri="/akn/example",
        )
        hit = {
            "document": doc,
            "position": 1,
            "best_match": False,
            "highlight": {},
            "pages": [],
            "provisions": [],
        }

        html = render_to_string(
            "peachjam_search/_search_hit.html",
            {
                "request": request,
                "hit": hit,
                "show_jurisdiction": False,
                "can_debug": False,
            },
            request=request,
        )

        self.assertIn('<ul class="list-unstyled flynotes my-2">', html)
        self.assertRegex(html, r"<li>\s*Line one\s*</li>")
        self.assertRegex(html, r"<li>\s*Line two\s*</li>")


class PortionSearchViewTest(TestCase):
    fixtures = ["tests/countries", "tests/users", "documents/sample_documents"]

    def setUp(self):
        self.request_factory = RequestFactory()

    def test_build_portions_falls_back_to_provision_inner_hits(self):
        expression_frbr_uri = "/akn/aa-au/act/charter/2007/elections-democracy-and-governance/eng@2007-01-30"
        search = Search()
        es_response = Response(
            search,
            {
                "_shards": {"failed": 0},
                "hits": {
                    "hits": [
                        {
                            "_score": 0.2,
                            "_source": {
                                "expression_frbr_uri": expression_frbr_uri,
                                "title": "Charter on Democracy, Elections and Governance",
                                "repealed": False,
                                "commenced": True,
                                "principal": True,
                            },
                            "inner_hits": {
                                "provisions": {
                                    "hits": {
                                        "hits": [
                                            {
                                                "_score": 0.25,
                                                "_source": {
                                                    "id": "sec_1",
                                                    "title": "Section 1",
                                                    "parent_ids": ["chp_1"],
                                                    "parent_titles": ["Chapter 1"],
                                                },
                                                "highlight": {
                                                    "provisions.body": [
                                                        "Foo <mark>bar</mark> baz"
                                                    ]
                                                },
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    ]
                },
            },
        )

        view = PortionSearchView()
        request = self.request_factory.get("/api/v1/search/portions")
        view.request = request

        with patch.object(view, "load_portion_details") as load_portion_details:
            portions = view.build_portions(es_response, request)

        self.assertEqual(1, len(portions))
        portion = portions[0]
        self.assertEqual("Foo bar baz", portion.content.text)
        self.assertEqual("provision", portion.metadata.portion_type)
        self.assertEqual("sec_1", portion.metadata.portion_id)
        self.assertEqual("Section 1", portion.metadata.portion_title)
        self.assertEqual(["chp_1"], portion.metadata.portion_parent_ids)
        self.assertEqual(["Chapter 1"], portion.metadata.portion_parent_titles)
        self.assertEqual(
            request.build_absolute_uri(f"{expression_frbr_uri}#sec_1"),
            portion.metadata.portion_public_url,
        )

        self.assertTrue(load_portion_details.called)
        provisions_to_load = load_portion_details.call_args[0][1]
        self.assertIn(
            "sec_1", [pid for ids in provisions_to_load.values() for pid in ids]
        )

    def test_build_portions_falls_back_to_page_inner_hits(self):
        expression_frbr_uri = "/akn/aa-au/act/charter/2007/elections-democracy-and-governance/eng@2007-01-30"
        search = Search()
        es_response = Response(
            search,
            {
                "_shards": {"failed": 0},
                "hits": {
                    "hits": [
                        {
                            "_score": 0.2,
                            "_source": {
                                "expression_frbr_uri": expression_frbr_uri,
                                "title": "Charter on Democracy, Elections and Governance",
                                "repealed": False,
                                "commenced": True,
                                "principal": True,
                            },
                            "inner_hits": {
                                "pages": {
                                    "hits": {
                                        "hits": [
                                            {
                                                "_score": 0.25,
                                                "_source": {"page_num": 12},
                                                "highlight": {
                                                    "pages.body": [
                                                        "Foo <mark>bar</mark> baz"
                                                    ]
                                                },
                                            }
                                        ]
                                    }
                                }
                            },
                        }
                    ]
                },
            },
        )

        view = PortionSearchView()
        request = self.request_factory.get("/api/v1/search/portions")
        view.request = request

        with patch.object(view, "load_portion_details") as load_portion_details:
            portions = view.build_portions(es_response, request)

        self.assertEqual(1, len(portions))
        portion = portions[0]
        self.assertEqual("Foo bar baz", portion.content.text)
        self.assertEqual("page", portion.metadata.portion_type)
        self.assertEqual("12", portion.metadata.portion_id)
        self.assertEqual(
            request.build_absolute_uri(f"{expression_frbr_uri}#page-12"),
            portion.metadata.portion_public_url,
        )

        self.assertTrue(load_portion_details.called)
        pages_to_load = load_portion_details.call_args[0][2]
        self.assertIn(12, [pid for ids in pages_to_load.values() for pid in ids])
