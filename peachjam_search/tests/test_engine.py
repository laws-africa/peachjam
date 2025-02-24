import json

from django.http import QueryDict
from django.test import TestCase  # noqa

from peachjam_search.engine import SearchEngine
from peachjam_search.forms import SearchForm


class TestEngine(TestCase):
    maxDiff = None

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
                        "excludes": [
                            "pages",
                            "content",
                            "flynote",
                            "case_summary",
                            "provisions",
                            "suggest",
                        ]
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
                        "_filter_date": {
                            "aggs": {
                                "date": {
                                    "date_histogram": {
                                        "field": "date",
                                        "interval": "year",
                                        "min_doc_count": 0,
                                    }
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
                        "_filter_registry": {
                            "aggs": {
                                "registry": {
                                    "terms": {"field": "registry", "size": 100}
                                }
                            },
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                        "_filter_year": {
                            "aggs": {"year": {"terms": {"field": "year", "size": 100}}},
                            "filter": {"terms": {"nature": ["Act"]}},
                        },
                    },
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
                            "minimum_should_match": 1,
                            "must": [{"term": {"is_most_recent": True}}],
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
