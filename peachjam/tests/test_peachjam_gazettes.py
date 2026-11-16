import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from peachjam.adapters import PeachjamGazetteAdapter
from peachjam.models import Gazette, Ingestor, Locality, SourceFile


@override_settings(DYNAMIC_STORAGE=None)
class PeachjamGazetteAdapterTest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=directory.name))
        self.extraction_patch = patch(
            "peachjam.models.DocumentContent.extract_content_from_source_file"
        )
        self.extraction_patch.start()
        self.addCleanup(self.extraction_patch.stop)
        self.ingestor = Ingestor.objects.create(
            name="Kenya Law gazettes", adapter="PeachjamGazetteAdapter", enabled=False
        )
        self.adapter = PeachjamGazetteAdapter(
            self.ingestor,
            {"api_url": "https://example.com/api/v1/", "token": "test-token"},
        )
        self.uri = (
            "/akn/ke/officialGazette/government-gazette/2026-11-13/200/eng@2026-11-13"
        )
        self.url = f"https://example.com/api/v1/gazettes{self.uri}"
        self.doc = {
            "expression_frbr_uri": self.uri,
            "language": "en",
            "date": "2026-11-13",
            "title": "Kenya Gazette Vol. CXXVIII-No. 200",
            "publication": "Kenya Gazette",
            "sub_publication": "Legal supplement",
            "supplement": True,
            "supplement_number": 3,
            "part": "I",
            "volume_number": "CXXVIII",
            "special": True,
            "published": True,
            "allow_robots": False,
        }
        self.pdf = b"%PDF-1.4\nfirst gazette\n%%EOF"
        self.adapter.client_get = Mock(side_effect=self.source_response)

    def source_response(self, url, **kwargs):
        if url == self.url:
            return SimpleNamespace(json=lambda: self.doc)
        if url == f"{self.url}/source.pdf":
            return SimpleNamespace(content=self.pdf)
        raise AssertionError(f"Unexpected URL: {url}")

    def test_first_refresh_and_incremental_pagination(self):
        next_page = "https://example.com/api/v1/gazettes?cursor=next"
        pages = [
            {"results": [self.doc], "next": next_page},
            {"results": [{"expression_frbr_uri": "another-gazette"}], "next": None},
        ]
        self.adapter.client_get.side_effect = [
            SimpleNamespace(json=lambda page=page: page) for page in pages
        ]
        self.assertEqual(
            self.adapter.check_for_updates(None), ([self.uri, "another-gazette"], [])
        )
        self.assertEqual(
            self.adapter.client_get.call_args_list[0].kwargs, {"params": {}}
        )
        self.assertEqual(self.adapter.client_get.call_args_list[1].args, (next_page,))

        since = datetime(2026, 11, 13, tzinfo=timezone.utc)
        self.adapter.settings["jurisdiction"] = "KE"
        self.adapter.client_get.side_effect = [
            SimpleNamespace(json=lambda: {"results": [], "next": None})
        ]
        self.assertEqual(self.adapter.check_for_updates(since), ([], []))
        self.adapter.client_get.assert_called_with(
            "https://example.com/api/v1/gazettes",
            params={"updated_at__gte": since.isoformat(), "jurisdiction": "KE"},
        )
        self.assertEqual(
            self.adapter.client.headers["Authorization"], "Token test-token"
        )

    def test_import_and_repeat_preserve_metadata_and_source_file(self):
        self.adapter.update_document(self.uri)
        gazette = Gazette.objects.get(expression_frbr_uri=self.uri)
        self.assertEqual(gazette.ingestor, self.ingestor)
        self.assertEqual(gazette.jurisdiction_id, "KE")
        for field in self.adapter.metadata_fields:
            self.assertEqual(getattr(gazette, field), self.doc[field])
        source = gazette.source_file
        self.assertEqual(source.source_url, f"{self.url}/source.pdf")
        self.assertEqual(source.sha256, hashlib.sha256(self.pdf).hexdigest())
        filename = source.file.name
        with source.file.open("rb") as file:
            self.assertEqual(file.read(), self.pdf)

        self.doc["title"] = "Updated Kenya Gazette"
        self.doc["published"] = False
        self.adapter.update_document(self.uri)
        self.assertEqual(Gazette.objects.count(), 1)
        self.assertEqual(SourceFile.objects.count(), 1)
        gazette.refresh_from_db()
        self.assertEqual(gazette.title, "Updated Kenya Gazette")
        self.assertFalse(gazette.published)
        self.assertEqual(gazette.source_file.file.name, filename)

    def test_changed_pdf_replaces_source_without_duplicating_document(self):
        self.adapter.update_document(self.uri)
        original_file = SourceFile.objects.get().file.name
        self.pdf = b"%PDF-1.4\ncorrected gazette\n%%EOF"
        self.adapter.update_document(self.uri)
        source = SourceFile.objects.get()
        self.assertNotEqual(source.file.name, original_file)
        self.assertEqual(source.size, len(self.pdf))
        self.assertEqual(source.sha256, hashlib.sha256(self.pdf).hexdigest())
        self.assertEqual(Gazette.objects.count(), 1)

    def test_real_pdf_import_extracts_and_saves_text(self):
        self.extraction_patch.stop()
        self.pdf = (
            Path(__file__).resolve().parents[1] / "fixtures/source_files/test.pdf"
        ).read_bytes()
        self.adapter.update_document(self.uri)
        gazette = Gazette.objects.get(expression_frbr_uri=self.uri)
        self.assertEqual(gazette.document_content.content_text.strip(), "test")

    def test_missing_source_document_is_skipped(self):
        self.adapter.client_get.side_effect = requests.HTTPError(
            response=SimpleNamespace(status_code=404)
        )
        self.adapter.update_document(self.uri)
        self.assertFalse(Gazette.objects.exists())
        self.adapter.client_get.assert_called_once_with(self.url)

    def test_detail_authentication_and_server_errors_are_not_swallowed(self):
        for status in [401, 403, 500, 503]:
            with self.subTest(status=status):
                self.adapter.client_get.side_effect = requests.HTTPError(
                    response=SimpleNamespace(status_code=status)
                )
                with self.assertRaises(requests.HTTPError):
                    self.adapter.update_document(self.uri)
                self.assertFalse(Gazette.objects.exists())

    def test_invalid_pdf_does_not_create_a_document(self):
        self.pdf = b"<html>Access denied</html>"
        with self.assertRaisesMessage(ValueError, "did not return a PDF"):
            self.adapter.update_document(self.uri)
        self.assertFalse(Gazette.objects.exists())

    def test_download_failure_leaves_existing_document_unchanged(self):
        self.adapter.update_document(self.uri)
        self.doc["title"] = "Should not be saved"
        for status in [404, 401, 403, 503]:
            with self.subTest(status=status):
                self.adapter.client_get.side_effect = [
                    SimpleNamespace(json=lambda: self.doc),
                    requests.HTTPError(response=SimpleNamespace(status_code=status)),
                ]
                with self.assertRaises(requests.HTTPError):
                    self.adapter.update_document(self.uri)
        self.assertEqual(
            Gazette.objects.get().title, "Kenya Gazette Vol. CXXVIII-No. 200"
        )

    def test_mismatched_source_identifier_is_rejected(self):
        self.doc["expression_frbr_uri"] = self.uri.replace("/200/", "/201/")
        with self.assertRaisesMessage(ValueError, "different gazette identifier"):
            self.adapter.update_document(self.uri)
        self.assertFalse(Gazette.objects.exists())

    def test_metadata_must_reproduce_the_source_identifier(self):
        self.doc["date"] = "2026-11-14"
        with self.assertRaisesMessage(
            ValueError, "does not match its source identifier"
        ):
            self.adapter.update_document(self.uri)
        self.assertFalse(Gazette.objects.exists())

    def test_locality_comes_from_source_uri_instead_of_remote_database_id(self):
        locality = Locality.objects.create(
            jurisdiction_id="KE", code="47", name="Nairobi"
        )
        self.uri = self.uri.replace("/ke/", "/ke-47/")
        self.url = f"https://example.com/api/v1/gazettes{self.uri}"
        self.doc["expression_frbr_uri"] = self.uri
        self.doc["locality"] = 999999
        self.adapter.update_document(self.uri)
        self.assertEqual(Gazette.objects.get().locality, locality)

    def test_file_save_failure_rolls_back_document(self):
        with patch.object(
            SourceFile, "save", side_effect=OSError("Storage unavailable")
        ):
            with self.assertRaises(OSError):
                self.adapter.update_document(self.uri)
        self.assertFalse(Gazette.objects.exists())


@override_settings(ROOT_URLCONF="peachjam.urls", DYNAMIC_STORAGE=None)
class GazetteAPITest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=directory.name))
        self.gazette = Gazette.objects.create(
            jurisdiction_id="KE",
            language_id="en",
            date=date(2026, 11, 13),
            title="Kenya Gazette",
            frbr_uri_number="200",
            frbr_uri_subtype="government-gazette",
            publication="Kenya Gazette",
            volume_number="CXXVIII",
            supplement=True,
            supplement_number=3,
            special=True,
            published=True,
        )
        self.pdf = b"%PDF-1.4\ngazette\n%%EOF"
        SourceFile.objects.create(
            document=self.gazette,
            file=ContentFile(self.pdf, name="gazette.pdf"),
            filename="gazette.pdf",
            mimetype="application/pdf",
        )
        self.user = get_user_model().objects.create_user(username="gazette-reader")
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="peachjam",
                codename="api_gazette",
            )
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_and_detail_include_gazette_metadata(self):
        response = self.client.get(reverse("gazettes-list"))
        self.assertEqual(response.status_code, 200)
        entry = response.json()["results"][0]
        self.assertEqual(entry["volume_number"], "CXXVIII")
        self.assertEqual(entry["supplement_number"], 3)
        self.assertTrue(entry["special"])
        self.assertTrue(entry["published"])
        response = self.client.get(
            reverse("api_gazette_detail", args=[self.gazette.expression_frbr_uri])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), entry)

    def test_pdf_route_accepts_full_expression_identifier(self):
        response = self.client.get(
            reverse("api_gazette_source_pdf", args=[self.gazette.expression_frbr_uri])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response.content, self.pdf)

    def test_gazette_endpoints_require_api_permission(self):
        user = get_user_model().objects.create_user(username="without-api-permission")
        urls = [
            reverse("gazettes-list"),
            reverse("api_gazette_detail", args=[self.gazette.expression_frbr_uri]),
            reverse("api_gazette_source_pdf", args=[self.gazette.expression_frbr_uri]),
        ]
        for account in [None, user]:
            self.client.force_authenticate(account)
            for url in urls:
                with self.subTest(account=account, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_missing_source_pdf_returns_404(self):
        self.gazette.source_file.delete()
        response = self.client.get(
            reverse("api_gazette_source_pdf", args=[self.gazette.expression_frbr_uri])
        )
        self.assertEqual(response.status_code, 404)
