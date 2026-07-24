import json
from dataclasses import replace
from unittest.mock import Mock, call, patch

from django.http import QueryDict
from django.test import TestCase  # noqa

from peachjam_search.compiler import ElasticsearchSearchCompiler
from peachjam_search.engine import (
    PortionSearchEngine,
    PortionSearchFilters,
    SearchEngine,
    make_portion_search_query,
)
from peachjam_search.forms import SearchForm
from peachjam_search.profiles import SearchProfile, SearchProfileSet
from peachjam_search.search_pipeline import (
    FilterClause,
    QueryAnalyser,
    QueryAnalysis,
    SearchPlanner,
)


class TestSearchEngine(TestCase):
    maxDiff = None

    def test_execute_runs_the_stateful_pipeline_in_order(self):
        engine = SearchEngine()
        stages = Mock()
        engine.analyse = stages.analyse
        engine.build_plan = stages.build_plan
        engine.compile = stages.compile
        engine.execute_search = stages.execute_search
        stages.execute_search.return_value = "response"

        self.assertEqual("response", engine.execute())
        self.assertEqual(
            [
                call.analyse(),
                call.build_plan(),
                call.compile(),
                call.execute_search(),
            ],
            stages.mock_calls,
        )

    def test_basic(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)

        search = engine.build_search()
        d = search.to_dict()
        self.assertEqual(
            json.dumps(
                {
                    "_source": {
                        "includes": [
                            "expression_frbr_uri",
                            "date",
                            "nature",
                            "doc_type",
                            "title",
                            "jurisdiction",
                            "locality",
                            "citation",
                            "authors",
                            "labels",
                            "alternative_names",
                            "flynote",
                            "blurb",
                            "court",
                            "matter_type",
                            "publication",
                            "sub_publication",
                        ],
                    },
                    "explain": False,
                    "from": 0,
                    "highlight": {
                        "fields": {
                            "alternative_names": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "citation": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "content": {
                                "fragment_size": 80,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 2,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "title": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                        }
                    },
                    "query": {
                        "bool": {
                            "filter": [{"term": {"is_most_recent": True}}],
                            "minimum_should_match": 1,
                            "should": [
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title^8"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title_expanded^3"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["citation^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["alternative_names^4"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["content"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["summary^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["flynote^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["blurb^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "match_phrase": {
                                        "content": {
                                            "boost": 4,
                                            "query": "test",
                                            "slop": 0,
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": ["pages.page_num"],
                                            "highlight": {
                                                "fields": {
                                                    "pages.body": {},
                                                    "pages.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "pages",
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["pages.body"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    }
                                                ],
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "pages.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": [
                                                "provisions.title",
                                                "provisions.id",
                                                "provisions.parent_titles",
                                                "provisions.parent_ids",
                                            ],
                                            "highlight": {
                                                "fields": {
                                                    "provisions.body": {},
                                                    "provisions.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "provisions",
                                        "query": {
                                            "bool": {
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "provisions.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.body"
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.title^4",
                                                                "provisions.parent_titles^2",
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                ]
                                            }
                                        },
                                    }
                                },
                            ],
                        }
                    },
                    "size": 10,
                    "sort": ["_score"],
                },
                indent=2,
                sort_keys=True,
            ),
            json.dumps(d, indent=2, sort_keys=True),
        )

    def test_debug_payload_includes_built_query(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)

        self.assertEqual(
            engine.build_search().to_dict(),
            engine.build_debug_payload()["query"],
        )

    @patch.object(
        ElasticsearchSearchCompiler, "get_query_embedding", return_value=[0.1, 0.2]
    )
    def test_portion_debug_payload_redacts_query_vector(self, mock_get_query_embedding):
        analyser = Mock()
        analyser.analyse.return_value = QueryAnalysis(
            raw_query="example search", clean_query="example search", intent="case_name"
        )
        engine = PortionSearchEngine(
            make_portion_search_query("example search", mode="semantic"),
            analyser=analyser,
        )

        payload = engine.build_debug_payload()

        analyser.analyse.assert_called_once_with("example search")
        self.assertEqual("case_name", engine.analysis.intent)
        self.assertIn("query_vector", json.dumps(payload["query"]))
        self.assertNotIn("0.1", json.dumps(payload["redacted_query"]))
        self.assertIn(
            "[embedding vector omitted]", json.dumps(payload["redacted_query"])
        )

    def test_portion_search_uses_standard_analysis_for_a_text_plan(self):
        self.assertIsInstance(
            PortionSearchEngine(make_portion_search_query("example search")).analyser,
            QueryAnalyser,
        )
        analyser = Mock()
        analyser.analyse.return_value = QueryAnalysis(
            raw_query="example search", clean_query="example search", intent="case_name"
        )
        engine = PortionSearchEngine(
            make_portion_search_query("example search"), analyser=analyser
        )

        plan = engine.build_plan()

        analyser.analyse.assert_called_once_with("example search")
        self.assertEqual("case_name", plan.analysis.intent)
        self.assertEqual("text", plan.mode)
        self.assertIsNone(plan.semantic_retrieval)
        self.assertIsNone(plan.rrf_retrieval)

    def test_basic_facets(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"
        params["nature"] = "Act"
        params["facets"] = "language"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)

        search = engine.build_search()
        d = search.to_dict()
        self.assertEqual(
            json.dumps(
                {
                    "_source": {
                        "includes": [
                            "expression_frbr_uri",
                            "date",
                            "nature",
                            "doc_type",
                            "title",
                            "jurisdiction",
                            "locality",
                            "citation",
                            "authors",
                            "labels",
                            "alternative_names",
                            "flynote",
                            "blurb",
                            "court",
                            "matter_type",
                            "publication",
                            "sub_publication",
                        ],
                    },
                    "aggs": {
                        "_filter_attorneys": {
                            "aggs": {
                                "attorneys": {
                                    "terms": {"field": "attorneys", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_authors": {
                            "aggs": {
                                "authors": {"terms": {"field": "authors", "size": 100}}
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_court": {
                            "aggs": {
                                "court": {"terms": {"field": "court", "size": 100}}
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_division": {
                            "aggs": {
                                "division": {
                                    "terms": {"field": "division", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_doc_type": {
                            "aggs": {
                                "doc_type": {
                                    "terms": {"field": "doc_type", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_judges": {
                            "aggs": {
                                "judges": {"terms": {"field": "judges", "size": 100}}
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_jurisdiction": {
                            "aggs": {
                                "jurisdiction": {
                                    "terms": {"field": "jurisdiction", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_labels": {
                            "aggs": {
                                "labels": {"terms": {"field": "labels", "size": 100}}
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_language": {
                            "aggs": {
                                "language": {
                                    "terms": {"field": "language", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_locality": {
                            "aggs": {
                                "locality": {
                                    "terms": {"field": "locality", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_matter_type": {
                            "aggs": {
                                "matter_type": {
                                    "terms": {"field": "matter_type", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_nature": {
                            "aggs": {
                                "nature": {"terms": {"field": "nature", "size": 100}}
                            },
                            "filter": {"match_all": {}},
                        },
                        "_filter_outcome": {
                            "aggs": {
                                "outcome": {"terms": {"field": "outcome", "size": 100}}
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_publication": {
                            "aggs": {
                                "publication": {
                                    "terms": {"field": "publication", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_case_action": {
                            "aggs": {
                                "case_action": {
                                    "terms": {"field": "case_action", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_registry": {
                            "aggs": {
                                "registry": {
                                    "terms": {"field": "registry", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_sub_publication": {
                            "aggs": {
                                "sub_publication": {
                                    "terms": {"field": "sub_publication", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_year": {
                            "aggs": {"year": {"terms": {"field": "year", "size": 100}}},
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                    },
                    "explain": False,
                    "from": 0,
                    "highlight": {
                        "fields": {
                            "alternative_names": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "citation": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "content": {
                                "fragment_size": 80,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 2,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "title": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                        }
                    },
                    "post_filter": {"terms": {"nature": ["Act"]}},
                    "query": {
                        "bool": {
                            "filter": [{"term": {"is_most_recent": True}}],
                            "minimum_should_match": 1,
                            "should": [
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title^8"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title_expanded^3"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["citation^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["alternative_names^4"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["content"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["summary^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["flynote^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["blurb^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "match_phrase": {
                                        "content": {
                                            "boost": 4,
                                            "query": "test",
                                            "slop": 0,
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": ["pages.page_num"],
                                            "highlight": {
                                                "fields": {
                                                    "pages.body": {},
                                                    "pages.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "pages",
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["pages.body"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    }
                                                ],
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "pages.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": [
                                                "provisions.title",
                                                "provisions.id",
                                                "provisions.parent_titles",
                                                "provisions.parent_ids",
                                            ],
                                            "highlight": {
                                                "fields": {
                                                    "provisions.body": {},
                                                    "provisions.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "provisions",
                                        "query": {
                                            "bool": {
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "provisions.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.body"
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.title^4",
                                                                "provisions.parent_titles^2",
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                ]
                                            }
                                        },
                                    }
                                },
                            ],
                        }
                    },
                    "size": 10,
                    "sort": ["_score"],
                },
                indent=2,
                sort_keys=True,
            ),
            json.dumps(d, indent=2, sort_keys=True),
        )

    def test_gazette_publication_filters(self):
        params = QueryDict("", mutable=True)
        params["publication"] = "Government Gazette"
        params["sub_publication"] = "Legal Notices A"
        params["facets"] = "1"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)

        search = engine.build_search()
        d = search.to_dict()

        self.assertEqual(
            ["Government Gazette"], engine.search_query.filters["publication"]
        )
        self.assertEqual(
            ["Legal Notices A"], engine.search_query.filters["sub_publication"]
        )
        self.assertIn("_filter_publication", d["aggs"])
        self.assertIn("_filter_sub_publication", d["aggs"])
        self.assertEqual(
            {"terms": {"field": "publication", "size": 100}},
            d["aggs"]["_filter_publication"]["aggs"]["publication"],
        )
        self.assertEqual(
            {"terms": {"field": "sub_publication", "size": 100}},
            d["aggs"]["_filter_sub_publication"]["aggs"]["sub_publication"],
        )

        post_filter = json.dumps(d["post_filter"], sort_keys=True)
        self.assertIn("publication", post_filter)
        self.assertIn("Government Gazette", post_filter)
        self.assertIn("sub_publication", post_filter)
        self.assertIn("Legal Notices A", post_filter)

    def test_static_default_profile_preserves_query(self):
        params = QueryDict("", mutable=True)
        params["search"] = "civil procedure code"

        unprofiled_engine = SearchEngine(planner=SearchPlanner(SearchProfileSet()))
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(unprofiled_engine)

        profiled_engine = SearchEngine(planner=SearchPlanner(SearchProfileSet()))
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(profiled_engine)
        self.assertEqual(
            unprofiled_engine.build_search().to_dict(),
            profiled_engine.build_search().to_dict(),
        )

    def test_analysis_override_selects_profile_from_profile_set(self):
        engine = SearchEngine(
            planner=SearchPlanner(
                SearchProfileSet(
                    labels={
                        "case_name": replace(SearchProfile.default(), name="case_name")
                    }
                )
            )
        )
        engine.set_search_query(replace(engine.search_query, query="Example v State"))
        engine.analysis = QueryAnalysis(
            raw_query="Example v State", intent="case_name", confidence=1.0
        )

        plan = engine.build_plan()

        self.assertEqual("Example v State", engine.search_query.query)
        self.assertEqual("case_name", plan.profile.name)
        self.assertEqual("case_name", plan.analysis.intent)

    def test_custom_search_profile_changes_query_parameters(self):
        params = QueryDict("", mutable=True)
        params["search"] = "civil procedure code"

        engine = SearchEngine(
            planner=SearchPlanner(
                SearchProfileSet(
                    default=replace(
                        SearchProfile.default(),
                        search_field_boosts={
                            "title": 12,
                            "title_expanded": 6,
                            "citation": 2,
                            "alternative_names": 4,
                            "content": 1,
                            "summary": 1,
                            "flynote": 1,
                            "blurb": 1,
                        },
                        phrase_match_content_boost=7,
                        phrase_match_slop=2,
                        simple_query_string_options={
                            "default_operator": "AND",
                            "minimum_should_match": "2<75%",
                        },
                        provision_title_boost=9,
                        provision_parent_titles_boost=3,
                    )
                )
            )
        )
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)
        query = json.dumps(engine.build_search().to_dict(), sort_keys=True)

        self.assertIn('"fields": ["title^12"]', query)
        self.assertIn('"fields": ["title_expanded^6"]', query)
        self.assertIn('"fields": ["summary"]', query)
        self.assertIn('"default_operator": "AND"', query)
        self.assertIn('"minimum_should_match": "2<75%"', query)
        self.assertIn('"boost": 7', query)
        self.assertIn('"slop": 2', query)
        self.assertIn('"provisions.title^9"', query)
        self.assertIn('"provisions.parent_titles^3"', query)

    def test_search_profile_can_override_pagerank_boost(self):
        engine = SearchEngine(
            planner=SearchPlanner(
                SearchProfileSet(
                    default=replace(
                        SearchProfile.default(),
                        use_pagerank_settings=False,
                        pagerank_boost_value=5,
                        pagerank_pivot_value=10,
                    )
                )
            )
        )

        query = engine.build_search().to_dict()["query"]

        self.assertEqual(
            {
                "rank_feature": {
                    "field": "ranking",
                    "boost": 5.0,
                    "saturation": {"pivot": 10},
                }
            },
            query["bool"]["must"][0],
        )

    def test_created_at(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"
        params["created_at__gte"] = "2025-01-01T00:00:00Z"
        params["nature"] = "Act"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)

        search = engine.build_search()
        d = search.to_dict()
        self.assertEqual(
            json.dumps(
                {
                    "_source": {
                        "includes": [
                            "expression_frbr_uri",
                            "date",
                            "nature",
                            "doc_type",
                            "title",
                            "jurisdiction",
                            "locality",
                            "citation",
                            "authors",
                            "labels",
                            "alternative_names",
                            "flynote",
                            "blurb",
                            "court",
                            "matter_type",
                            "publication",
                            "sub_publication",
                        ],
                    },
                    "explain": False,
                    "from": 0,
                    "highlight": {
                        "fields": {
                            "alternative_names": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "citation": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "content": {
                                "fragment_size": 80,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 2,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "title": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                        }
                    },
                    "post_filter": {"terms": {"nature": ["Act"]}},
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"is_most_recent": True}},
                                {
                                    "range": {
                                        "created_at": {"gte": "2025-01-01T00:00:00Z"}
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                            "should": [
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title^8"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["title_expanded^3"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["citation^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["alternative_names^4"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["content"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["summary^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["flynote^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "simple_query_string": {
                                        "default_operator": "OR",
                                        "fields": ["blurb^2"],
                                        "minimum_should_match": "4<80%",
                                        "query": "test",
                                    }
                                },
                                {
                                    "match_phrase": {
                                        "content": {
                                            "boost": 4,
                                            "query": "test",
                                            "slop": 0,
                                        }
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": ["pages.page_num"],
                                            "highlight": {
                                                "fields": {
                                                    "pages.body": {},
                                                    "pages.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "pages",
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["pages.body"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    }
                                                ],
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "pages.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                },
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": [
                                                "provisions.title",
                                                "provisions.id",
                                                "provisions.parent_titles",
                                                "provisions.parent_ids",
                                            ],
                                            "highlight": {
                                                "fields": {
                                                    "provisions.body": {},
                                                    "provisions.body.exact": {},
                                                },
                                                "fragment_size": 80,
                                                "max_analyzed_offset": 999999,
                                                "number_of_fragments": 2,
                                                "post_tags": ["</mark>"],
                                                "pre_tags": ["<mark>"],
                                            },
                                        },
                                        "path": "provisions",
                                        "query": {
                                            "bool": {
                                                "should": [
                                                    {
                                                        "match_phrase": {
                                                            "provisions.body": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.body"
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                            "quote_field_suffix": ".exact",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "provisions.title^4",
                                                                "provisions.parent_titles^2",
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                ]
                                            }
                                        },
                                    }
                                },
                            ],
                        }
                    },
                    "size": 10,
                    "sort": ["_score"],
                },
                indent=2,
                sort_keys=True,
            ),
            json.dumps(d, indent=2, sort_keys=True),
        )

    def test_semantic(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"
        params["nature"] = "Act"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)
        engine.set_search_query(replace(engine.search_query, mode="semantic"))

        with patch.object(
            engine.compiler, "get_query_embedding", return_value=[0.1, 0.2]
        ):
            search = engine.build_search()

        d = search.to_dict()
        self.assertEqual(
            json.dumps(
                {
                    "_source": {
                        "includes": [
                            "expression_frbr_uri",
                            "date",
                            "nature",
                            "doc_type",
                            "title",
                            "jurisdiction",
                            "locality",
                            "citation",
                            "authors",
                            "labels",
                            "alternative_names",
                            "flynote",
                            "blurb",
                            "court",
                            "matter_type",
                            "publication",
                            "sub_publication",
                        ],
                    },
                    "explain": False,
                    "from": 0,
                    "highlight": {
                        "fields": {
                            "alternative_names": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "citation": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "content": {
                                "fragment_size": 80,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 2,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "title": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                        }
                    },
                    "post_filter": {"terms": {"nature": ["Act"]}},
                    "query": {
                        "bool": {
                            "filter": [{"term": {"is_most_recent": True}}],
                            "must": [
                                {
                                    "nested": {
                                        "inner_hits": {
                                            "_source": {
                                                "excludes": [
                                                    "content_chunks.text_embedding"
                                                ]
                                            }
                                        },
                                        "path": "content_chunks",
                                        "query": {
                                            "knn": {
                                                "field": "content_chunks.text_embedding",
                                                "k": 150,
                                                "num_candidates": 1500,
                                                "query_vector": [0.1, 0.2],
                                                "similarity": 0.4,
                                            }
                                        },
                                        "score_mode": "max",
                                    }
                                }
                            ],
                        }
                    },
                    "size": 10,
                    "sort": ["_score"],
                },
                indent=2,
                sort_keys=True,
            ),
            json.dumps(d, indent=2, sort_keys=True),
        )

    def test_hybrid(self):
        params = QueryDict("", mutable=True)
        params["search"] = "test"
        params["nature"] = "Act"

        engine = SearchEngine()
        form = SearchForm(params)
        self.assertTrue(form.is_valid())
        form.configure_engine(engine)
        engine.set_search_query(replace(engine.search_query, mode="hybrid"))

        with patch.object(
            engine.compiler, "get_query_embedding", return_value=[0.1, 0.2]
        ):
            search = engine.build_search()

        d = search.to_dict()
        self.assertEqual(
            json.dumps(
                {
                    "_source": {
                        "includes": [
                            "expression_frbr_uri",
                            "date",
                            "nature",
                            "doc_type",
                            "title",
                            "jurisdiction",
                            "locality",
                            "citation",
                            "authors",
                            "labels",
                            "alternative_names",
                            "flynote",
                            "blurb",
                            "court",
                            "matter_type",
                            "publication",
                            "sub_publication",
                        ]
                    },
                    "explain": False,
                    "from": 0,
                    "highlight": {
                        "fields": {
                            "alternative_names": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "citation": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "content": {
                                "fragment_size": 80,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 2,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                            "title": {
                                "fragment_size": 0,
                                "max_analyzed_offset": 999999,
                                "number_of_fragments": 0,
                                "post_tags": ["</mark>"],
                                "pre_tags": ["<mark>"],
                            },
                        }
                    },
                    "post_filter": {"terms": {"nature": ["Act"]}},
                    "retriever": {
                        "rrf": {
                            "rank_constant": 60,
                            "rank_window_size": 150,
                            "retrievers": [
                                {
                                    "standard": {
                                        "_name": "text",
                                        "query": {
                                            "bool": {
                                                "filter": [
                                                    {"term": {"is_most_recent": True}}
                                                ],
                                                "minimum_should_match": 1,
                                                "should": [
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["title^8"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "title_expanded^3"
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["citation^2"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": [
                                                                "alternative_names^4"
                                                            ],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["content"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["summary^2"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["flynote^2"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "simple_query_string": {
                                                            "default_operator": "OR",
                                                            "fields": ["blurb^2"],
                                                            "minimum_should_match": "4<80%",
                                                            "query": "test",
                                                        }
                                                    },
                                                    {
                                                        "match_phrase": {
                                                            "content": {
                                                                "boost": 4,
                                                                "query": "test",
                                                                "slop": 0,
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "nested": {
                                                            "inner_hits": {
                                                                "_source": [
                                                                    "pages.page_num"
                                                                ],
                                                                "highlight": {
                                                                    "fields": {
                                                                        "pages.body": {},
                                                                        "pages.body.exact": {},
                                                                    },
                                                                    "fragment_size": 80,
                                                                    "max_analyzed_offset": 999999,
                                                                    "number_of_fragments": 2,
                                                                    "post_tags": [
                                                                        "</mark>"
                                                                    ],
                                                                    "pre_tags": [
                                                                        "<mark>"
                                                                    ],
                                                                },
                                                            },
                                                            "path": "pages",
                                                            "query": {
                                                                "bool": {
                                                                    "must": [
                                                                        {
                                                                            "simple_query_string": {
                                                                                "default_operator": "OR",
                                                                                "fields": [
                                                                                    "pages.body"
                                                                                ],
                                                                                "minimum_should_match": "4<80%",
                                                                                "query": "test",
                                                                                "quote_field_suffix": ".exact",
                                                                            }
                                                                        }
                                                                    ],
                                                                    "should": [
                                                                        {
                                                                            "match_phrase": {
                                                                                "pages.body": {
                                                                                    "boost": 4,
                                                                                    "query": "test",
                                                                                    "slop": 0,
                                                                                }
                                                                            }
                                                                        }
                                                                    ],
                                                                }
                                                            },
                                                        }
                                                    },
                                                    {
                                                        "nested": {
                                                            "inner_hits": {
                                                                "_source": [
                                                                    "provisions.title",
                                                                    "provisions.id",
                                                                    "provisions.parent_titles",
                                                                    "provisions.parent_ids",
                                                                ],
                                                                "highlight": {
                                                                    "fields": {
                                                                        "provisions.body": {},
                                                                        "provisions.body.exact": {},
                                                                    },
                                                                    "fragment_size": 80,
                                                                    "max_analyzed_offset": 999999,
                                                                    "number_of_fragments": 2,
                                                                    "post_tags": [
                                                                        "</mark>"
                                                                    ],
                                                                    "pre_tags": [
                                                                        "<mark>"
                                                                    ],
                                                                },
                                                            },
                                                            "path": "provisions",
                                                            "query": {
                                                                "bool": {
                                                                    "should": [
                                                                        {
                                                                            "match_phrase": {
                                                                                "provisions.body": {
                                                                                    "boost": 4,
                                                                                    "query": "test",
                                                                                    "slop": 0,
                                                                                }
                                                                            }
                                                                        },
                                                                        {
                                                                            "simple_query_string": {
                                                                                "default_operator": "OR",
                                                                                "fields": [
                                                                                    "provisions.body"
                                                                                ],
                                                                                "minimum_should_match": "4<80%",
                                                                                "query": "test",
                                                                                "quote_field_suffix": ".exact",
                                                                            }
                                                                        },
                                                                        {
                                                                            "simple_query_string": {
                                                                                "default_operator": "OR",
                                                                                "fields": [
                                                                                    "provisions.title^4",
                                                                                    "provisions.parent_titles^2",
                                                                                ],
                                                                                "minimum_should_match": "4<80%",
                                                                                "query": "test",
                                                                            }
                                                                        },
                                                                    ]
                                                                }
                                                            },
                                                        }
                                                    },
                                                ],
                                            }
                                        },
                                    }
                                },
                                {
                                    "standard": {
                                        "_name": "semantic",
                                        "filter": [{"term": {"is_most_recent": True}}],
                                        "query": {
                                            "bool": {
                                                "must": [
                                                    {
                                                        "nested": {
                                                            "inner_hits": {
                                                                "_source": {
                                                                    "excludes": [
                                                                        "content_chunks.text_embedding"
                                                                    ]
                                                                }
                                                            },
                                                            "path": "content_chunks",
                                                            "query": {
                                                                "knn": {
                                                                    "field": "content_chunks.text_embedding",
                                                                    "k": 150,
                                                                    "num_candidates": 1500,
                                                                    "query_vector": [
                                                                        0.1,
                                                                        0.2,
                                                                    ],
                                                                    "similarity": 0.4,
                                                                }
                                                            },
                                                            "score_mode": "max",
                                                        }
                                                    }
                                                ]
                                            }
                                        },
                                    }
                                },
                            ],
                        }
                    },
                    "size": 10,
                },
                indent=2,
                sort_keys=True,
            ),
            json.dumps(d, indent=2, sort_keys=True),
        )

    def test_portion_filter_conversion_and_hybrid_pipeline(self):
        filters = [
            PortionSearchFilters(frbr_doctype="act", principal=True),
            PortionSearchFilters(work_frbr_uri__in=["/akn/za/act/1"]),
        ]
        search_query = make_portion_search_query(
            "example search", filters, mode="hybrid"
        )
        self.assertEqual(
            (
                FilterClause("frbr_uri_doctype", "term", "act"),
                FilterClause("principal", "term", True),
                FilterClause("work_frbr_uri", "terms", ("/akn/za/act/1",)),
            ),
            search_query.hard_filters,
        )

        analyser = Mock()
        analyser.analyse.return_value = QueryAnalysis(
            raw_query="example search", clean_query="example search", intent="case_name"
        )
        engine = PortionSearchEngine(
            search_query,
            planner=SearchPlanner(semantic_k=5),
            analyser=analyser,
        )
        with patch.object(
            engine.compiler, "get_query_embedding", return_value=[0.1, 0.2]
        ):
            search = engine.build_search()

        self.assertIsInstance(engine.planner, SearchPlanner)
        self.assertEqual("case_name", engine.analysis.intent)
        self.assertEqual(5, engine.plan.semantic_retrieval.k)
        self.assertEqual(50, engine.plan.semantic_retrieval.num_candidates)
        self.assertEqual(150, engine.plan.rrf_retrieval.rank_window_size)

        query = search.to_dict()
        self.assertEqual(0, query["from"])
        self.assertEqual(10, query["size"])
        self.assertFalse(query["explain"])
        retrievers = query["retriever"]["rrf"]["retrievers"]
        expected_filters = [
            {"term": {"is_most_recent": True}},
            {"term": {"frbr_uri_doctype": "act"}},
            {"term": {"principal": True}},
            {"terms": {"work_frbr_uri": ["/akn/za/act/1"]}},
        ]
        self.assertEqual(
            expected_filters,
            retrievers[0]["standard"]["query"]["bool"]["filter"],
        )
        self.assertEqual(expected_filters, retrievers[1]["standard"]["filter"])
