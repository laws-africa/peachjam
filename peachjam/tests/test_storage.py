import datetime
import re
import unittest.util
from unittest.mock import ANY, Mock, call

from countries_plus.models import Country
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from languages_plus.models import Language

from peachjam.models import CoreDocument, SourceFile
from peachjam.storage import DynamicS3Boto3Storage

# don't truncate diff strings
# see https://stackoverflow.com/questions/43842675/how-to-prevent-truncating-of-string-in-unit-test-python
unittest.util._MAX_LENGTH = 999999999


class Pattern:
    def __init__(self, p):
        self.p = p if isinstance(p, re.Match) else re.compile(p)

    def __eq__(self, other):
        return self.p.match(other)

    def __neq__(self, other):
        return not self.p.match(other)


class TestableStorage(DynamicS3Boto3Storage):
    pass


@override_settings(
    DYNAMIC_STORAGE={
        "DEFAULTS": {"": "s3:fake-bucket:"},
        "PREFIXES": {"s3": {"storage": "peachjam.tests.test_storage.TestableStorage"}},
    }
)
class DynamicS3StorageTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]
    maxDiff = None

    def setUp(self):
        self.doc = CoreDocument.objects.create(
            title="test document",
            jurisdiction=Country.objects.get(pk="ZA"),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="document",
            frbr_uri_number="test",
            date=datetime.date(2022, 1, 1),
        )
        self.mock = TestableStorage.connection = Mock()

    def test_basics(self):
        sf = SourceFile(document=self.doc)
        sf.filename = "test.txt"
        sf.mimetype = "text/plain"
        sf.file = ContentFile(b"test data", "test.txt")
        sf.save()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object(
                    Pattern(
                        rf"media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt"
                    )
                ),
                call.Bucket().Object().upload_fileobj(ANY, ExtraArgs=ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.assertRegex(
            list(SourceFile.objects.filter(pk=sf.pk).values_list("file", flat=True))[0],
            rf"s3:fake-bucket:media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt",
        )
        self.assertRegex(
            sf.file.get_raw_value(),
            rf"s3:fake-bucket:media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt",
        )

        self.mock.reset_mock()

        sf.file.readlines()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object(
                    Pattern(
                        rf"media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt"
                    )
                ),
                call.Bucket().Object().load(),
                call.Bucket().Object().download_fileobj(ANY, ExtraArgs=ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.mock.reset_mock()

        sf.refresh_from_db()
        sf.file.readlines()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object(
                    Pattern(
                        rf"media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt"
                    )
                ),
                call.Bucket().Object().load(),
                call.Bucket().Object().download_fileobj(ANY, ExtraArgs=ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.mock.reset_mock()

        sf.refresh_from_db()
        sf.file.size()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object(
                    Pattern(
                        rf"media/core_document/{self.doc.pk}/source_file/[^/]+/test\.txt"
                    )
                ),
                call.Bucket().Object().content_length(),
            ],
            self.mock.mock_calls,
        )


@override_settings(
    DYNAMIC_STORAGE={
        "DEFAULTS": {"": "file:"},
        "PREFIXES": {"file": {"storage": "peachjam.storage.DynamicFileSystemStorage"}},
    }
)
class DynamicFileSystemStorageTestCase(TestCase):
    fixtures = ["tests/countries", "tests/languages"]
    maxDiff = None

    def setUp(self):
        self.doc = CoreDocument.objects.create(
            title="test document",
            jurisdiction=Country.objects.get(pk="ZA"),
            language=Language.objects.get(pk="en"),
            frbr_uri_doctype="document",
            frbr_uri_number="test",
            date=datetime.date(2022, 1, 1),
        )

    def test_basics(self):
        sf = SourceFile(document=self.doc)
        sf.filename = "test.txt"
        sf.mimetype = "text/plain"
        sf.file = ContentFile(b"test data", "test.txt")
        sf.save()

        self.assertEqual([b"test data"], sf.file.readlines())

        sf.refresh_from_db()
        self.assertEqual([b"test data"], sf.file.readlines())
        self.assertEqual(9, sf.file.size)
        self.assertEqual(f"file:{sf.file.name}", sf.file.get_raw_value())

    def test_get_set_raw(self):
        sf = SourceFile(document=self.doc)
        sf.filename = "test.txt"
        sf.mimetype = "text/plain"
        sf.file = ContentFile(b"test data", "test.txt")
        sf.save()
        sf.refresh_from_db()
        self.assertEqual(f"file:{sf.file.name}", sf.file.get_raw_value())

        sf.file.set_raw_value("file:foo/bar.txt")
        self.assertEqual("file:foo/bar.txt", sf.file.get_raw_value())
        sf.refresh_from_db()
        self.assertEqual("file:foo/bar.txt", sf.file.get_raw_value())
