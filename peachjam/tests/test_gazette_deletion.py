from datetime import date
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from peachjam.adapters import PeachjamGazetteDeleteAdapter
from peachjam.models import Gazette, Ingestor, SourceFile


@override_settings(DYNAMIC_STORAGE=None)
class GazetteDeletionTest(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def setUp(self):
        self.ingestor = Ingestor.objects.create(
            name="Kenya Law deletions",
            adapter="PeachjamGazetteDeleteAdapter",
            enabled=False,
        )
        self.adapter = PeachjamGazetteDeleteAdapter(
            self.ingestor,
            {"api_url": "https://example.com/api/v1", "token": "test-token"},
        )
        self.kenya = self.create_gazette("KE", "1")
        self.other_kenya = self.create_gazette("KE", "2")
        self.south_africa = self.create_gazette("ZA", "1")
        self.adapter.client_get = Mock()
        self.adapter.client_post = Mock()

    def create_gazette(self, country, number):
        return Gazette.objects.create(
            jurisdiction_id=country,
            language_id="en",
            date=date(2026, 11, 13),
            title=f"Gazette {number}",
            frbr_uri_number=number,
        )

    def missing(self, status=404):
        return requests.HTTPError(response=SimpleNamespace(status_code=status))

    def test_batches_only_kenyan_gazettes_including_shared_history(self):
        self.adapter.settings["batch_range"] = "1"
        self.adapter.settings["jurisdiction"] = "ZA"
        with patch("peachjam.tasks.get_deleted_documents") as queue:
            self.assertEqual(self.adapter.check_for_updates(None), ([], []))
        self.assertEqual(
            queue.call_args_list,
            [
                call(self.ingestor.pk, self.kenya.pk, self.kenya.pk),
                call(self.ingestor.pk, self.other_kenya.pk, self.other_kenya.pk),
            ],
        )
        self.assertIsNone(self.kenya.ingestor_id)
        self.assertEqual(
            list(self.adapter.queryset().order_by("pk")), [self.kenya, self.other_kenya]
        )

    def test_invalid_batch_size_is_rejected(self):
        self.adapter.settings["batch_range"] = "0"
        with self.assertRaisesMessage(ValueError, "batch_range must be positive"):
            self.adapter.check_for_updates(None)

    def test_validation_only_queues_missing_submitted_identifiers(self):
        self.adapter.client_post.return_value.json.return_value = {
            "invalid_expression_frbr_uris": [
                self.kenya.expression_frbr_uri,
                self.kenya.expression_frbr_uri,
                self.south_africa.expression_frbr_uri,
                "/akn/ke/officialGazette/1900-01-01/unsubmitted/eng@1900-01-01",
            ]
        }
        with patch("peachjam.tasks.delete_document") as queue:
            self.adapter.get_deleted_documents(self.kenya.pk, self.other_kenya.pk)
        self.adapter.client_post.assert_called_once_with(
            "https://example.com/api/v1/validate-gazette-expression-frbr-uris",
            json={
                "expression_frbr_uris": [
                    self.kenya.expression_frbr_uri,
                    self.other_kenya.expression_frbr_uri,
                ]
            },
        )
        queue.assert_called_once_with(self.ingestor.pk, self.kenya.expression_frbr_uri)
        self.assertEqual(Gazette.objects.count(), 3)

    def test_empty_batch_does_not_call_source(self):
        self.adapter.get_deleted_documents(self.south_africa.pk, self.south_africa.pk)
        self.adapter.client_post.assert_not_called()

    def test_validation_error_does_not_queue_deletions(self):
        self.adapter.client_post.side_effect = self.missing(503)
        with patch("peachjam.tasks.delete_document") as queue:
            with self.assertRaises(requests.HTTPError):
                self.adapter.get_deleted_documents(self.kenya.pk, self.other_kenya.pk)
        queue.assert_not_called()

    def test_deletions_between_batches_do_not_skip_remaining_gazettes(self):
        third_kenya = self.create_gazette("KE", "3")
        self.adapter.settings["batch_range"] = "1"
        expected = [
            self.kenya.expression_frbr_uri,
            self.other_kenya.expression_frbr_uri,
            third_kenya.expression_frbr_uri,
        ]
        with patch("peachjam.tasks.get_deleted_documents") as queue:
            self.adapter.check_for_updates(None)
        self.adapter.client_post.return_value.json.return_value = {
            "invalid_expression_frbr_uris": expected
        }
        self.adapter.client_get.side_effect = self.missing()
        with patch(
            "peachjam.tasks.delete_document",
            side_effect=lambda ingestor_id, uri: self.adapter.delete_document(uri),
        ):
            for batch in queue.call_args_list:
                self.adapter.get_deleted_documents(*batch.args[1:])
        submitted = [
            uri
            for request in self.adapter.client_post.call_args_list
            for uri in request.kwargs["json"]["expression_frbr_uris"]
        ]
        self.assertEqual(submitted, expected)
        self.assertFalse(Gazette.objects.filter(jurisdiction_id="KE").exists())
        self.assertTrue(Gazette.objects.filter(pk=self.south_africa.pk).exists())

    def test_delete_rechecks_source_and_only_removes_missing_kenyan_record(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with override_settings(MEDIA_ROOT=directory.name):
            source = SourceFile.objects.create(
                document=self.kenya,
                file=ContentFile(b"%PDF-1.4", name="shared.pdf"),
                filename="shared.pdf",
                mimetype="application/pdf",
            )
            self.adapter.client_get.side_effect = self.missing()
            self.adapter.delete_document(self.kenya.expression_frbr_uri)
            self.assertFalse(Gazette.objects.filter(pk=self.kenya.pk).exists())
            # Deleting a local record must not remove a potentially shared PDF object.
            self.assertTrue(source.file.storage.exists(source.file.name))
        self.assertTrue(Gazette.objects.filter(pk=self.other_kenya.pk).exists())
        self.assertTrue(Gazette.objects.filter(pk=self.south_africa.pk).exists())

    def test_reappeared_document_is_not_deleted(self):
        self.adapter.delete_document(self.kenya.expression_frbr_uri)
        self.adapter.client_get.assert_called_once_with(
            f"https://example.com/api/v1/gazettes{self.kenya.expression_frbr_uri}"
        )
        self.assertTrue(Gazette.objects.filter(pk=self.kenya.pk).exists())

    def test_non_kenyan_document_is_not_checked_or_deleted(self):
        self.adapter.client_get.side_effect = self.missing()
        self.adapter.delete_document(self.south_africa.expression_frbr_uri)
        self.adapter.client_get.assert_not_called()
        self.assertTrue(Gazette.objects.filter(pk=self.south_africa.pk).exists())

    def test_source_errors_never_delete_local_records(self):
        for error in [
            self.missing(401),
            self.missing(403),
            self.missing(500),
            requests.ConnectionError(),
        ]:
            with self.subTest(error=error):
                self.adapter.client_get.side_effect = error
                with self.assertRaises(requests.RequestException):
                    self.adapter.delete_document(self.kenya.expression_frbr_uri)
                self.assertTrue(Gazette.objects.filter(pk=self.kenya.pk).exists())
