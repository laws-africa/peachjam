import datetime
import unittest.util
from unittest.mock import ANY, Mock, call

from countries_plus.models import Country
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from languages_plus.models import Language

from peachjam.models import CoreDocument, SourceFile
from peachjam.storage import DynamicS3Boto3Storage


class TestableStorage(DynamicS3Boto3Storage):
    pass


# don't truncate diff strings
# see https://stackoverflow.com/questions/43842675/how-to-prevent-truncating-of-string-in-unit-test-python
unittest.util._MAX_LENGTH = 999999999


@override_settings(
    DYNAMIC_STORAGE={
        "PREFIXES": {
            "s3": {
                "storage": "peachjam.tests.test_storage.TestableStorage",
            }
        },
        "DEFAULTS": {"": "s3:fake-bucket:"},
    }
)
class DynamicStorageTestCase(TestCase):
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
        cf = ContentFile(b"test data", "test.txt")
        sf.file = cf
        sf.save()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object("media/core_document/1/source_file/test.txt"),
                call.Bucket().Object().upload_fileobj(cf, ExtraArgs=ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.assertEqual(
            ["s3:fake-bucket:media/core_document/1/source_file/test.txt"],
            list(SourceFile.objects.filter(pk=sf.pk).values_list("file", flat=True)),
        )

        self.mock.reset_mock()

        sf.file.readlines()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object("media/core_document/1/source_file/test.txt"),
                call.Bucket().Object().load(),
                call.Bucket().Object().download_fileobj(ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.mock.reset_mock()

        sf.refresh_from_db()
        sf.file.readlines()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object("media/core_document/1/source_file/test.txt"),
                call.Bucket().Object().load(),
                call.Bucket().Object().download_fileobj(ANY, Config=ANY),
            ],
            self.mock.mock_calls,
        )

        self.mock.reset_mock()

        sf.refresh_from_db()
        sf.file.size()
        self.assertEqual(
            [
                call.Bucket("fake-bucket"),
                call.Bucket().Object("media/core_document/1/source_file/test.txt"),
                call.Bucket().Object().content_length(),
            ],
            self.mock.mock_calls,
        )
