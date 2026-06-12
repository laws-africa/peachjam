import datetime
import os
from types import SimpleNamespace
from unittest.mock import patch

import requests
from countries_plus.models import Country
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils.text import slugify
from languages_plus.models import Language

from peachjam.adapters import (
    IndigoAdapter,
    IndigoEnrichmentDatasetIngestor,
    JudgmentAdapter,
)
from peachjam.models import (
    Court,
    GenericDocument,
    Judgment,
    Legislation,
    ProvisionTopicEnrichment,
    SourceFile,
    Taxonomy,
)


class IndigoAdapterTest(TestCase):
    maxDiff = None
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        self.adapter = IndigoAdapter(
            None,
            {"token": "XXX", "api_url": "http://example.com", "places": "za za-cpt"},
        )
        self.adapter.place_codes = ["za", "za-cpt"]

    def test_is_responsible_for_places(self):
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za-cpt/act/2009/1"))

        self.assertFalse(self.adapter.is_responsible_for("/akn/bw/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za-xxx/act/2009/1"))

    def test_is_responsible_for_include_doctypes(self):
        self.adapter.include_doctypes = ["act"]

        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1")
        )

    def test_is_responsible_for_exclude_doctypes(self):
        self.adapter.exclude_doctypes = ["act"]

        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/judgment/zahc/1999/1"))

    def test_is_responsible_for_include_subtypes(self):
        self.adapter.include_subtypes = ["by-law"]

        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_exclude_subtypes(self):
        self.adapter.exclude_subtypes = ["by-law"]

        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/2009/1"))
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/thing/1999/1"))

    def test_is_responsible_for_include_actors(self):
        self.adapter.include_actors = ["foo"]

        self.assertTrue(
            self.adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1")
        )
        self.assertFalse(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1")
        )

    def test_is_responsible_for_exclude_actors(self):
        self.adapter.exclude_actors = ["foo"]

        self.assertFalse(
            self.adapter.is_responsible_for("/akn/za/act/by-law/foo/2009/1")
        )
        self.assertTrue(self.adapter.is_responsible_for("/akn/za/act/by-law/2009/1"))
        self.assertTrue(
            self.adapter.is_responsible_for("/akn/za/act/by-law/bar/1999/1")
        )

    def test_import_taxonomy_tree(self):
        self.adapter.taxonomy_topic_root = "src1:dest1 src2:dest2"

        src_tree = [
            {
                "name": "src1",
                "slug": "src1",
                "children": [
                    {
                        "name": "child-1",
                        "slug": "src1-child-1",
                        "children": [],
                    },
                    {
                        "name": "child-2",
                        "slug": "src1-child-2",
                        "children": [],
                    },
                ],
            },
            {
                "name": "src2",
                "slug": "src2",
                "children": [
                    {
                        "name": "child-a",
                        "slug": "src2-child-a",
                        "children": [],
                    },
                    {
                        "name": "child-b",
                        "slug": "src2-child-b",
                        "children": [],
                    },
                ],
            },
        ]
        self.adapter.get_taxonomy_tree = lambda: src_tree

        # pre-populate dest1 and dest2 locally
        Taxonomy.load_bulk(
            [
                {
                    "data": {
                        "name": "dest1",
                        "slug": "dest1",
                    },
                    "children": [],
                },
                {
                    "data": {
                        "name": "dest2",
                        "slug": "dest2",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-a",
                                "slug": "dest2-child-a",
                            },
                        },
                        {
                            # this must be deleted
                            "data": {
                                "name": "child-z",
                                "slug": "dest2-child-z",
                            }
                        },
                    ],
                },
            ]
        )

        # dest1 will be empty locally, and dest2 will have some topics and some which must be deleted
        src_mapping, tree_mapping = self.adapter.import_taxonomy_tree()

        self.assertEqual(
            {
                "src1": "dest1",
                "src2": "dest2",
            },
            src_mapping,
        )

        self.assertEqual(
            {
                "src1-child-1": Taxonomy.objects.get(slug="dest1-child-1"),
                "src1-child-2": Taxonomy.objects.get(slug="dest1-child-2"),
                "src2-child-a": Taxonomy.objects.get(slug="dest2-child-a"),
                "src2-child-b": Taxonomy.objects.get(slug="dest2-child-b"),
            },
            tree_mapping,
        )

        def simplify(entries):
            # keep only necessary data fields for comparison
            for entry in entries:
                entry["data"] = {
                    k: v for k, v in entry["data"].items() if k in ["name", "slug"]
                }
                simplify(entry.get("children", []))

        local_tree = Taxonomy.dump_bulk(
            parent=Taxonomy.objects.get(slug="dest1"), keep_ids=False
        )
        simplify(local_tree)
        self.assertEqual(
            [
                {
                    "data": {
                        "name": "dest1",
                        "slug": "dest1",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-1",
                                "slug": "dest1-child-1",
                            }
                        },
                        {
                            "data": {
                                "name": "child-2",
                                "slug": "dest1-child-2",
                            }
                        },
                    ],
                }
            ],
            local_tree,
        )

        local_tree = Taxonomy.dump_bulk(
            parent=Taxonomy.objects.get(slug="dest2"), keep_ids=False
        )
        simplify(local_tree)
        self.assertEqual(
            [
                {
                    "data": {
                        "name": "dest2",
                        "slug": "dest2",
                    },
                    "children": [
                        {
                            "data": {
                                "name": "child-a",
                                "slug": "dest2-child-a",
                            }
                        },
                        {
                            "data": {
                                "name": "child-b",
                                "slug": "dest2-child-b",
                            }
                        },
                    ],
                }
            ],
            local_tree,
        )

    def test_enrichment_dataset_ingestor_imports_provision_topics(self):
        document = Legislation.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=datetime.date(2024, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="act",
            frbr_uri_number="1",
            title="Arbitration Act",
            metadata_json={"commenced": True},
        )
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        taxonomy_tree = {
            "results": [
                {
                    "name": "Enrichments",
                    "slug": "enrichments",
                    "children": [
                        {
                            "name": "Arbitration law",
                            "slug": "enrichments-arbitration-law",
                            "children": [
                                {
                                    "name": "Validity",
                                    "slug": "enrichments-arbitration-law-validity",
                                    "children": [],
                                },
                                {
                                    "name": "Recognition",
                                    "slug": "arbitration-law-recognition",
                                    "children": [],
                                },
                            ],
                        }
                    ],
                }
            ]
        }
        dataset = {
            "enrichments": [
                {
                    "work": document.work.frbr_uri,
                    "provision_id": "sec_1",
                    "taxonomy_topic": "arbitration-law-validity",
                }
            ]
        }

        Taxonomy.load_bulk(
            [
                {
                    "data": {
                        "name": "Enrichments arbitration law",
                    },
                    "children": [],
                }
            ]
        )

        adapter.client_get = lambda url: SimpleNamespace(  # noqa: E731
            json=lambda: taxonomy_tree if url.endswith("/taxonomy-topics") else dataset
        )

        adapter.import_dataset()

        topic = Taxonomy.objects.get(slug="enrichments-arbitration-law-validity")
        Taxonomy.objects.get(slug="enrichments-arbitration-law-recognition")
        enrichment = ProvisionTopicEnrichment.objects.get()
        self.assertEqual(document.work, enrichment.work)
        self.assertEqual("sec_1", enrichment.provision_eid)
        self.assertEqual(topic, enrichment.topic)

    def test_enrichment_dataset_ingestor_check_for_updates_returns_dataset_sentinel(
        self,
    ):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        adapter.get_dataset = lambda: {  # noqa: E731
            "updated_at": "2024-01-02T00:00:00Z",
            "enrichments": [],
        }

        last_refreshed = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        updated, deleted = adapter.check_for_updates(last_refreshed)

        self.assertEqual([adapter.DATASET_DOCUMENT_ID], updated)
        self.assertEqual([], deleted)

    def test_enrichment_dataset_ingestor_check_for_updates_checks_works_when_dataset_fresh(
        self,
    ):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        adapter.get_dataset = lambda: {  # noqa: E731
            "updated_at": "2024-01-01T00:00:00Z",
            "enrichments": [
                {
                    "work": "/akn/za/act/2024/1",
                    "provision_id": "sec_1",
                    "taxonomy_topic": "arbitration-law-validity",
                }
            ],
        }
        adapter.get_work = lambda work_frbr_uri: {  # noqa: E731
            "url": "http://example.com/akn/za/act/2024/1/eng@2024-01-01",
            "updated_at": "2024-01-03T00:00:00Z",
            "points_in_time": [
                {
                    "expressions": [
                        {
                            "url": "http://example.com/akn/za/act/2024/1/eng@2024-01-01",
                            "updated_at": "2024-01-03T00:00:00Z",
                        },
                        {
                            "url": "http://example.com/akn/za/act/2024/1/fra@2024-01-01",
                            "updated_at": "2024-01-03T00:00:00Z",
                        },
                    ]
                }
            ],
        }

        last_refreshed = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        updated, deleted = adapter.check_for_updates(last_refreshed)

        self.assertEqual(
            [
                "http://example.com/akn/za/act/2024/1/eng@2024-01-01",
                "http://example.com/akn/za/act/2024/1/fra@2024-01-01",
            ],
            sorted(updated),
        )
        self.assertEqual([], deleted)

    def test_enrichment_dataset_ingestor_queues_missing_local_work(self):
        document = Legislation.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=datetime.date(2024, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="act",
            frbr_uri_number="1",
            title="Existing Act",
            metadata_json={"commenced": True},
        )
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        adapter.get_dataset = lambda: {  # noqa: E731
            "updated_at": "2024-01-01T00:00:00Z",
            "enrichments": [
                {"work": document.work_frbr_uri},
                {"work": "/akn/za/act/2024/2"},
            ],
        }
        adapter.get_work = lambda work_frbr_uri: {  # noqa: E731
            "url": f"http://example.com{work_frbr_uri}/eng@2024-01-01",
            "updated_at": "2024-01-01T00:00:00Z",
            "points_in_time": [],
        }

        last_refreshed = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        updated, deleted = adapter.check_for_updates(last_refreshed)

        self.assertEqual(
            ["http://example.com/akn/za/act/2024/2/eng@2024-01-01"],
            updated,
        )
        self.assertEqual([], deleted)

    def test_enrichment_dataset_ingestor_skips_unchanged_existing_work(self):
        document = Legislation.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=datetime.date(2024, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="act",
            frbr_uri_number="1",
            title="Existing Act",
            metadata_json={"commenced": True},
        )
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        adapter.get_dataset = lambda: {  # noqa: E731
            "updated_at": "2024-01-01T00:00:00Z",
            "enrichments": [{"work": document.work_frbr_uri}],
        }
        adapter.get_work = lambda work_frbr_uri: {  # noqa: E731
            "url": f"http://example.com{work_frbr_uri}/eng@2024-01-01",
            "updated_at": "2024-01-01T00:00:00Z",
            "points_in_time": [],
        }

        last_refreshed = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        updated, deleted = adapter.check_for_updates(last_refreshed)

        self.assertEqual([], updated)
        self.assertEqual([], deleted)

    def test_enrichment_dataset_ingestor_skips_missing_remote_work(self):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        response = SimpleNamespace(status_code=404)
        adapter.get_dataset = lambda: {  # noqa: E731
            "updated_at": "2024-01-01T00:00:00Z",
            "enrichments": [{"work": "/akn/za/act/2024/1"}],
        }

        def get_work(work_frbr_uri):
            raise requests.exceptions.HTTPError(response=response)

        adapter.get_work = get_work

        last_refreshed = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
        updated, deleted = adapter.check_for_updates(last_refreshed)

        self.assertEqual([], updated)
        self.assertEqual([], deleted)

    def test_enrichment_dataset_ingestor_update_document_imports_dataset(self):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )

        with patch.object(adapter, "import_dataset") as import_dataset:
            adapter.update_document(adapter.DATASET_DOCUMENT_ID)

        import_dataset.assert_called_once_with()

    def test_enrichment_dataset_ingestor_update_document_delegates_document_urls(self):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )

        with patch.object(IndigoAdapter, "update_document") as update_document:
            adapter.update_document(
                "http://example.com/akn/za/act/2024/1/eng@2024-01-01"
            )

        update_document.assert_called_once_with(
            "http://example.com/akn/za/act/2024/1/eng@2024-01-01"
        )

    def test_enrichment_dataset_ingestor_requires_local_taxonomy_root(self):
        adapter = IndigoEnrichmentDatasetIngestor(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "dataset_id": "5",
                "taxonomy_topic_root": "enrichments-arbitration-law:enrichments-arbitration-law",
            },
        )
        taxonomy_tree = {
            "results": [
                {
                    "name": "Arbitration law",
                    "slug": "enrichments-arbitration-law",
                    "children": [],
                }
            ]
        }
        dataset = {"enrichments": []}

        adapter.client_get = lambda url: SimpleNamespace(  # noqa: E731
            json=lambda: taxonomy_tree if url.endswith("/taxonomy-topics") else dataset
        )

        with self.assertRaisesMessage(
            ValueError,
            "Taxonomy root enrichments-arbitration-law not found locally",
        ):
            adapter.import_dataset()

    @patch("peachjam.adapters.indigo.SourceFile.track_changes", autospec=True)
    def test_download_source_file_creates_tracked_source_file(self, track_changes):
        document = GenericDocument.objects.create(
            jurisdiction=Country.objects.get(pk="ZA"),
            date=datetime.date(2022, 1, 1),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="doc",
            title="Fixture PDF",
        )
        with open(
            os.path.abspath("peachjam/fixtures/source_files/test.pdf"),
            "rb",
        ) as fixture:
            pdf_content = fixture.read()

        self.adapter.client_get = lambda url: SimpleNamespace(  # noqa: E731
            content=pdf_content,
            headers={},
        )

        self.adapter.download_source_file(
            "http://example.com/source.pdf",
            document,
            "Fixture PDF",
        )

        document.refresh_from_db()
        source_file = SourceFile.objects.get(document=document)
        self.assertEqual("fixture-pdf.pdf", source_file.filename)
        self.assertEqual("application/pdf", source_file.mimetype)
        self.assertEqual(len(pdf_content), source_file.size)
        track_changes.assert_called_once_with(source_file)


class JudgmentAdapterTest(TestCase):
    fixtures = ["tests/countries", "tests/languages", "tests/courts"]

    def setUp(self):
        self.adapter = JudgmentAdapter(
            None,
            {
                "token": "XXX",
                "api_url": "http://example.com",
                "court_code": "eacj",
            },
        )

    def remote_judgment_doc(self, **overrides):
        doc = {
            "title": "Remote judgment",
            "case_name": "Foo v Bar",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "citation": "Remote citation",
            "work_frbr_uri": "/akn/za/judgment/eacj/2024/1",
            "expression_frbr_uri": "/akn/za/judgment/eacj/2024/1/eng@2024-01-01",
            "jurisdiction": "ZA",
            "language": "en",
            "court": {"code": "EACJ", "name": "East African Court of Justice"},
            "registry": None,
            "locality": None,
            "serial_number": 1,
            "serial_number_override": None,
            "mnc": "[2024] EACJ 1",
            "date": "2024-01-01",
            "allow_robots": True,
            "published": True,
            "flynote": "Remote flynote",
            "flynote_raw": "Remote flynote raw",
            "case_summary": "<p>Remote summary</p>",
            "case_summary_public": True,
            "blurb": "Remote blurb",
            "issues": ["Issue 1"],
            "held": ["Held 1"],
            "order": "Remote order",
            "summary_ai_generated": True,
            "summary_generated_at": "2024-01-03T00:00:00Z",
            "summary_language": "English",
            "summary_trace_id": "trace-123",
            "case_numbers": [],
            "judges": [],
            "topics": [],
        }
        doc.update(overrides)
        return doc

    @patch("peachjam.adapters.judgments.SourceFile.track_changes", autospec=True)
    @patch("peachjam.adapters.judgments.SourceFile.ensure_file_as_pdf", autospec=True)
    def test_attach_source_file_creates_tracked_source_file(
        self, ensure_file_as_pdf, track_changes
    ):
        judgment = Judgment.objects.create(
            language=Language.objects.get(pk="en"),
            court=Court.objects.first(),
            date=datetime.date(2022, 1, 1),
            jurisdiction=Country.objects.get(pk="ZA"),
            case_name="Fixture judgment",
        )
        with open(
            os.path.abspath("peachjam/fixtures/source_files/test.pdf"),
            "rb",
        ) as fixture:
            pdf_content = fixture.read()

        self.adapter.client_get = lambda url: SimpleNamespace(  # noqa: E731
            content=pdf_content,
        )

        self.adapter.attach_source_file(
            {
                "expression_frbr_uri": judgment.expression_frbr_uri,
                "title": judgment.title,
            },
            judgment,
        )

        judgment.refresh_from_db()
        source_file = SourceFile.objects.get(document=judgment)
        self.assertEqual(
            f"{os.path.splitext(slugify(judgment.title))[0]}.pdf",
            source_file.filename,
        )
        self.assertEqual("application/pdf", source_file.mimetype)
        track_changes.assert_called_once_with(source_file)
        ensure_file_as_pdf.assert_called_once_with(source_file)

    @patch("peachjam.models.judgment.generate_judgment_summary")
    def test_update_document_imports_summary_fields(self, generate_summary):
        doc = self.remote_judgment_doc()

        self.adapter.client_get = lambda url: SimpleNamespace(
            json=lambda: doc
        )  # noqa: E731
        self.adapter.get_content_html = (
            lambda doc: "<p>Remote content</p>"
        )  # noqa: E731
        self.adapter.attach_source_file = lambda doc, created_doc: None  # noqa: E731

        self.adapter.update_document(
            "http://example.com/judgments/akn/za/judgment/eacj/2024/1/eng@2024-01-01"
        )

        judgment = Judgment.objects.get(expression_frbr_uri=doc["expression_frbr_uri"])
        self.assertEqual("<p>Remote summary</p>", judgment.case_summary)
        self.assertEqual(True, judgment.case_summary_public)
        self.assertEqual("Remote blurb", judgment.blurb)
        self.assertEqual("Remote flynote raw", judgment.flynote_raw)
        self.assertEqual("Remote flynote", judgment.flynote)
        self.assertEqual(["Issue 1"], judgment.issues)
        self.assertEqual(["Held 1"], judgment.held)
        self.assertEqual("Remote order", judgment.order)
        self.assertTrue(judgment.summary_ai_generated)
        self.assertEqual("English", judgment.summary_language)
        self.assertEqual("trace-123", judgment.summary_trace_id)
        self.assertIsNotNone(judgment.summary_generated_at)
        generate_summary.assert_not_called()

    @override_settings(PEACHJAM={**settings.PEACHJAM, "SUMMARISER_LANGUAGE": "English"})
    @patch("peachjam.models.judgment.generate_judgment_summary")
    def test_update_document_skips_wrong_language_ai_summary(self, generate_summary):
        doc = self.remote_judgment_doc(summary_language="French")

        self.adapter.client_get = lambda url: SimpleNamespace(
            json=lambda: doc
        )  # noqa: E731
        self.adapter.get_content_html = (
            lambda doc: "<p>Remote content</p>"
        )  # noqa: E731
        self.adapter.attach_source_file = lambda doc, created_doc: None  # noqa: E731

        self.adapter.update_document(
            "http://example.com/judgments/akn/za/judgment/eacj/2024/1/eng@2024-01-01"
        )

        judgment = Judgment.objects.get(expression_frbr_uri=doc["expression_frbr_uri"])
        self.assertIsNone(judgment.case_summary)
        self.assertFalse(judgment.case_summary_public)
        self.assertIsNone(judgment.blurb)
        self.assertIsNone(judgment.issues)
        self.assertIsNone(judgment.held)
        self.assertIsNone(judgment.order)
        self.assertFalse(judgment.summary_ai_generated)
        self.assertIsNone(judgment.summary_generated_at)
        self.assertEqual("English", judgment.summary_language)
        self.assertIsNone(judgment.summary_trace_id)
        self.assertTrue(
            any(call.args == (judgment.pk,) for call in generate_summary.call_args_list)
        )
