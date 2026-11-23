from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve

from gazettes.views import YearView, global_year_not_found
from peachjam.views import GazetteYearView


@override_settings(ROOT_URLCONF="gazettes.urls")
class GazetteYearUrlTest(SimpleTestCase):
    def test_global_gazette_list_redirects_home(self):
        for url in ["/gazettes", "/gazettes/"]:
            with self.subTest(url=url):
                match = resolve(url, urlconf="gazettes.urls")
                response = match.func(RequestFactory().get(url), **match.kwargs)

                self.assertEqual(302, response.status_code)
                self.assertEqual("/", response.url)

    def test_global_year_page_is_disabled(self):
        match = resolve("/gazettes/2024", urlconf="gazettes.urls")

        self.assertEqual(global_year_not_found, match.func)
        with self.assertRaises(Http404):
            match.func(RequestFactory().get("/gazettes/2024"), **match.kwargs)

    def test_jurisdiction_year_page_is_available(self):
        match = resolve("/gazettes/za/2024", urlconf="gazettes.urls")

        self.assertEqual(YearView, match.func.view_class)

    def test_shared_global_year_page_remains_available(self):
        match = resolve("/gazettes/2024", urlconf="peachjam.urls")

        self.assertEqual(GazetteYearView, match.func.view_class)


class ArchiveStorageConfigTests(SimpleTestCase):
    def test_archive_owner_remains_writable_without_changing_consumer_defaults(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        from django.conf import settings

        from peachjam import settings as core_settings
        from peachjam.models import SourceFile
        from peachjam.storage import DynamicS3Boto3Storage

        bucket = "lawsafrica-gazettes-archive"
        self.assertTrue(
            core_settings.DYNAMIC_STORAGE["PREFIXES"]["s3"]["buckets"][bucket][
                "silent_readonly"
            ]
        )
        self.assertFalse(
            settings.DYNAMIC_STORAGE["PREFIXES"]["s3"]["buckets"][bucket][
                "silent_readonly"
            ]
        )
        storage = DynamicS3Boto3Storage(
            name=f"s3:{bucket}:archive/za/test.pdf",
            access_key="s3-key",
            secret_key="s3-secret",
        )
        self.assertFalse(storage.silent_readonly)
        source = SimpleNamespace(
            source_url=None,
            file=SimpleNamespace(storage=storage, name="archive/za/test.pdf"),
            filename_for_download=lambda: "gazette.pdf",
        )
        with patch.object(storage.connection.meta.client, "copy_object") as copy:
            SourceFile.set_download_filename(source)
        self.assertEqual(copy.call_args.kwargs["Bucket"], bucket)
