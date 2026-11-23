from datetime import date
from importlib import import_module
from unittest.mock import patch

from countries_plus.models import Country
from django.db import connection
from django.test import TestCase
from languages_plus.models import Language

from peachjam.models import CoreDocument


class GazetteSourceURLMigrationTests(TestCase):
    fixtures = ["tests/countries", "tests/languages"]

    def test_clears_only_gazette_service_urls_with_nonempty_archive_file_references(
        self,
    ):
        archive_file = "s3:lawsafrica-gazettes-archive:archive/za/test.pdf"
        cases = [
            ("https://gazettes.africa/akn/za/test/source", archive_file, True, True),
            ("http://gazettes.africa/akn/za/test/source", archive_file, True, True),
            (
                "https://archive.gazettes.africa/archive/za/test.pdf",
                archive_file,
                True,
                True,
            ),
            (
                "https://www.gazettes.africa/akn/za/test/source",
                archive_file,
                True,
                True,
            ),
            ("HTTPS://GAZETTES.AFRICA/test", archive_file, True, True),
            ("https://gazettes.africa:443/test", archive_file, True, True),
            ("https://gazettes.africa?download=1", archive_file, True, True),
            ("https://example.org/document.pdf", archive_file, True, False),
            ("https://gazettes.africa.example.org/test", archive_file, True, False),
            ("https://gazettes.africa@evil.example/test", archive_file, True, False),
            ("https://notgazettes.africa/test", archive_file, True, False),
            ("https://gazettes.africa/test", "s3:another-bucket:test.pdf", True, False),
            (
                "https://gazettes.africa/test",
                "s3:lawsafrica-gazettes-archive:",
                True,
                False,
            ),
            (
                "https://gazettes.africa/test",
                "s3:lawsafrica-gazettes-archive-extra:test.pdf",
                True,
                False,
            ),
            ("https://gazettes.africa/test", "", True, False),
            ("https://gazettes.africa/test", "file:local.pdf", True, False),
            ("https://gazettes.africa/test", archive_file, False, False),
            (None, archive_file, True, False),
            ("", archive_file, True, False),
        ]
        expected = {}
        for number, (url, file, gazette, clear) in enumerate(cases):
            document = CoreDocument.objects.create(
                title=f"Gazette {number}",
                jurisdiction=Country.objects.get(pk="ZA"),
                language=Language.objects.get(pk="en"),
                frbr_uri_doctype="officialGazette" if gazette else "document",
                frbr_uri_number=f"gazette-migration-{number}",
                date=date(2026, 11, 23),
                source_url="https://original.example/publication",
            )
            # Insert raw values exactly as stored, without touching DynamicStorageFileField.
            with connection.cursor() as cursor:
                if gazette:
                    cursor.execute(
                        """INSERT INTO peachjam_gazette (coredocument_ptr_id, supplement, special)
                           VALUES (%s, false, false)""",
                        [document.pk],
                    )
                cursor.execute(
                    """INSERT INTO peachjam_sourcefile
                       (document_id, filename, mimetype, size, file, source_url,
                        file_as_pdf, anonymised_file_as_pdf, file_is_anonymised)
                       VALUES (%s, 'test.pdf', 'application/pdf', 123, %s, %s, '', '', false)
                       RETURNING id""",
                    [document.pk, file, url],
                )
                source_id = cursor.fetchone()[0]
            expected[source_id] = (
                None if clear else url,
                file,
                "test.pdf",
                "application/pdf",
                123,
            )

        migration = import_module("peachjam.migrations.0329_clear_gazette_source_urls")
        with (
            patch(
                "peachjam.storage.DynamicStorageFieldFile.__init__",
                side_effect=AssertionError("No file access"),
            ),
            patch(
                "peachjam.models.SourceFile.save",
                side_effect=AssertionError("No model saves"),
            ),
            patch(
                "botocore.client.BaseClient._make_api_call",
                side_effect=AssertionError("No storage requests"),
            ),
            connection.cursor() as cursor,
        ):
            # Repeat to check idempotence as well as the exact raw column values.
            for _ in range(2):
                cursor.execute(migration.Migration.operations[0].sql)
                cursor.execute(
                    "SELECT id, source_url, file, filename, mimetype, size FROM peachjam_sourcefile WHERE id = ANY(%s)",
                    [list(expected)],
                )
                actual = {row[0]: row[1:] for row in cursor.fetchall()}
                self.assertEqual(actual, expected)
            cursor.execute(
                """SELECT DISTINCT source_url FROM peachjam_coredocument
                   WHERE id IN (SELECT document_id FROM peachjam_sourcefile WHERE id = ANY(%s))""",
                [list(expected)],
            )
            self.assertEqual(
                cursor.fetchall(), [("https://original.example/publication",)]
            )

    def test_importing_an_existing_s3_reference_does_not_write_object_metadata(self):
        from django.core.files.base import ContentFile
        from storages.backends.s3boto3 import S3Boto3Storage

        from peachjam.models import SourceFile

        document = CoreDocument.objects.create(
            title="Imported gazette",
            jurisdiction=Country.objects.get(pk="ZA"),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="officialGazette",
            frbr_uri_number="existing-archive-reference",
            date=date(2026, 11, 23),
        )
        path = "s3:lawsafrica-gazettes-archive:archive/za/test.pdf"
        source = SourceFile(
            document=document,
            file=path,
            filename="test.pdf",
            mimetype="application/pdf",
            size=123,
        )
        with (
            patch.object(
                S3Boto3Storage,
                "_open",
                return_value=ContentFile(b"PDF", name="test.pdf"),
            ) as open_file,
            patch.object(
                S3Boto3Storage, "_save", side_effect=AssertionError("No uploads")
            ),
            patch.object(
                SourceFile,
                "set_download_filename",
                side_effect=AssertionError("No metadata writes"),
            ),
        ):
            source.save()
            # The adapter restores the raw reference after the dynamic field strips its prefix.
            SourceFile.objects.filter(pk=source.pk).update(file=path)
        open_file.assert_called_once()
        self.assertIsNone(source.source_url)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT file FROM peachjam_sourcefile WHERE id = %s", [source.pk]
            )
            self.assertEqual(cursor.fetchone()[0], path)
