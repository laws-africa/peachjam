import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from elasticsearch_dsl.response import Response

from peachjam_search.documents import MultiLanguageIndexManager
from peachjam_search.engine import SearchEngine
from peachjam_search.profiles import get_default_search_profile_set


class RunSearchCommandTest(SimpleTestCase):
    def response(self, search):
        return Response(
            search,
            {
                "_shards": {"failed": 0},
                "hits": {
                    "total": {"value": 1},
                    "hits": [
                        {
                            "_id": "12",
                            "_index": "tanzlii_eng",
                            "_score": 42.5,
                            "_source": {
                                "expression_frbr_uri": "/akn/tz/act/1985/9/eng@2024-10-11",
                                "work_frbr_uri": "/akn/tz/act/1985/9",
                                "title": "Criminal Procedure Act",
                                "citation": "Act 9 of 1985",
                                "summary": "Judgment summary text",
                                "flynote": "Flynote text",
                                "blurb": "Blurb text",
                                "principal": True,
                                "commenced": True,
                                "repealed": False,
                            },
                            "highlight": {"content": ["A <em>criminal</em> snippet"]},
                            "inner_hits": {
                                "pages": {
                                    "hits": {
                                        "hits": [
                                            {
                                                "_score": 3.5,
                                                "_source": {"page_num": 2},
                                                "highlight": {
                                                    "pages.body": [
                                                        "Page <em>match</em>"
                                                    ]
                                                },
                                            }
                                        ]
                                    }
                                },
                                "provisions": {
                                    "hits": {
                                        "hits": [
                                            {
                                                "_score": 4.5,
                                                "_source": {
                                                    "id": "sec_2",
                                                    "title": "Section 2",
                                                    "parent_ids": ["chp_1"],
                                                    "parent_titles": ["Chapter 1"],
                                                },
                                                "highlight": {
                                                    "provisions.body": [
                                                        "Provision <em>match</em>"
                                                    ]
                                                },
                                            }
                                        ]
                                    }
                                },
                            },
                            "_explanation": {"value": 42.5, "description": "test"},
                        }
                    ],
                },
            },
        )

    @patch("peachjam_search.compiler.RetrieverSearch.execute", autospec=True)
    def test_outputs_rich_review_json(self, mock_execute):
        mock_execute.side_effect = self.response

        stdout = io.StringIO()
        call_command(
            "run_search",
            "criminal procedure act",
            "--intent",
            "act_name",
            "--site-url",
            "https://tanzlii.org",
            "--explain",
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual("act_name", payload["analysis"]["intent"])
        self.assertIn("compiled_query", payload)
        self.assertEqual(1, payload["total_hits"])
        self.assertEqual(1, payload["returned_hits"])

        result = payload["results"][0]
        self.assertEqual(1, result["position"])
        self.assertEqual("/akn/tz/act/1985/9", result["work_frbr_uri"])
        self.assertEqual("Criminal Procedure Act", result["source"]["title"])
        self.assertEqual("Judgment summary text", result["source"]["summary"])
        self.assertEqual("Flynote text", result["source"]["flynote"])
        self.assertEqual("Blurb text", result["source"]["blurb"])
        self.assertEqual(
            "https://tanzlii.org/akn/tz/act/1985/9/eng@2024-10-11",
            result["url"],
        )
        self.assertEqual(2, result["page_matches"][0]["page_num"])
        self.assertEqual("sec_2", result["provision_matches"][0]["id"])
        self.assertEqual(42.5, result["explanation"]["value"])

    @patch("peachjam_search.compiler.RetrieverSearch.execute", autospec=True)
    def test_index_prefixes_and_search_form_params(self, mock_execute):
        mock_execute.side_effect = self.response

        stdout = io.StringIO()
        call_command(
            "run_search",
            "criminal procedure act",
            "--intent",
            "act_name",
            "--ordering",
            "date",
            "--index-prefix",
            "tanzlii",
            "--param",
            "nature=Act",
            "--param",
            "nature=Judgment",
            "--param",
            "search__title=Criminal Procedure Act",
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(
            [
                "tanzlii",
                *[
                    f"tanzlii_{language}"
                    for language in MultiLanguageIndexManager.ANALYZERS
                ],
            ],
            payload["indexes"],
        )
        self.assertEqual(["Act", "Judgment"], payload["inputs"]["filters"]["nature"])
        self.assertEqual("date", payload["inputs"]["ordering"])
        self.assertEqual(
            "Criminal Procedure Act", payload["inputs"]["field_queries"]["title"]
        )

        stdout = io.StringIO()
        call_command(
            "run_search",
            "criminal procedure act",
            "--intent",
            "act_name",
            stdout=stdout,
        )
        self.assertEqual(
            SearchEngine().compiler.index,
            json.loads(stdout.getvalue())["indexes"],
        )

    @patch("peachjam_search.compiler.RetrieverSearch.execute", autospec=True)
    def test_profile_and_intent_select_label_profile_and_write_output(
        self, mock_execute
    ):
        mock_execute.side_effect = self.response
        profile_set = get_default_search_profile_set().to_dict()
        profile_set["labels"]["case_name"] = {
            **profile_set["default"],
            "name": "review-case-name",
        }

        with TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profiles.json"
            output_path = Path(tmpdir) / "result.json"
            profile_path.write_text(json.dumps(profile_set), encoding="utf-8")

            stdout = io.StringIO()
            call_command(
                "run_search",
                "Example v State",
                "--intent",
                "case_name",
                "--profile",
                str(profile_path),
                "--output",
                str(output_path),
                stdout=stdout,
            )

            self.assertEqual(f"Wrote {output_path}\n", stdout.getvalue())
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual("case_name", payload["analysis"]["intent"])
        self.assertEqual("review-case-name", payload["plan"]["profile"]["name"])

    def test_rejects_invalid_params_and_profiles(self):
        with self.assertRaisesMessage(CommandError, "expected KEY=VALUE"):
            call_command("run_search", "test", "--param", "not-a-param")

        with self.assertRaisesMessage(CommandError, "Could not read profile file"):
            call_command("run_search", "test", "--profile", "/does/not/exist.json")

        with self.assertRaises(CommandError):
            call_command("run_search", "test", "--intent", "unknown")
