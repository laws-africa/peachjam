from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from peachjam.models import SourceFile
from peachjam.storage import DynamicS3Boto3Storage, S3Storage
from peachjam.views.documents import DocumentSourcePDFView


@override_settings(
    R2_DOWNLOAD_BUCKETS={"primary-bucket": "mirror-bucket"},
    R2_ENDPOINT_URL="https://account.r2.cloudflarestorage.com",
    R2_ACCESS_KEY_ID="r2-key",
    R2_SECRET_ACCESS_KEY="r2-secret",
    DYNAMIC_STORAGE={
        "PREFIXES": {"s3": {"storage": "peachjam.storage.DynamicS3Boto3Storage"}}
    },
)
class R2DownloadTests(SimpleTestCase):
    def storage(self, klass=S3Storage, bucket="primary-bucket", **kwargs):
        if klass is DynamicS3Boto3Storage:
            kwargs["name"] = f"s3:{bucket}:media/test.pdf"
        return klass(
            bucket_name=bucket,
            access_key="s3-key",
            secret_key="s3-secret",
            endpoint_url="https://s3.eu-west-1.amazonaws.com",
            region_name="eu-west-1",
            signature_version="s3v4",
            querystring_auth=True,
            querystring_expire=300,
            **kwargs,
        )

    def test_standard_and_dynamic_urls_sign_for_r2_without_network_requests(self):
        for klass in (S3Storage, DynamicS3Boto3Storage):
            with (
                self.subTest(storage=klass),
                patch(
                    "botocore.client.BaseClient._make_api_call",
                    side_effect=AssertionError(
                        "Signing must not make network requests"
                    ),
                ),
            ):
                storage = self.storage(klass, location="prefix")
                url = urlsplit(storage.url("media/a file.pdf"))
                query = parse_qs(url.query)
                self.assertEqual(url.hostname, "account.r2.cloudflarestorage.com")
                self.assertEqual(
                    unquote(url.path), "/mirror-bucket/prefix/media/a file.pdf"
                )
                self.assertEqual(query["X-Amz-Expires"], ["300"])
                self.assertTrue(query["X-Amz-Signature"])
                self.assertEqual(query["X-Amz-Credential"][0].split("/")[0], "r2-key")
                self.assertIn("/auto/s3/aws4_request", query["X-Amz-Credential"][0])
                # The main connection and persisted bucket identity remain on S3.
                self.assertEqual(storage.bucket_name, "primary-bucket")
                self.assertEqual(
                    storage.connection.meta.client.meta.endpoint_url,
                    "https://s3.eu-west-1.amazonaws.com",
                )

    def test_url_parameters_and_explicit_expiry_are_preserved(self):
        storage = self.storage()
        params = {"ResponseContentDisposition": "inline"}
        query = parse_qs(
            urlsplit(storage.url("test.pdf", parameters=params, expire=120)).query
        )
        self.assertEqual(query["X-Amz-Expires"], ["120"])
        self.assertEqual(query["response-content-disposition"], ["inline"])
        self.assertEqual(params, {"ResponseContentDisposition": "inline"})
        with patch.object(
            storage.r2_download_storage, "url", return_value="signed"
        ) as url:
            self.assertEqual(storage.url("test.pdf", params, 120, "HEAD"), "signed")
            url.assert_called_once_with("test.pdf", params, 120, "HEAD")

    @override_settings(
        AWS_SESSION_TOKEN="aws-session-token", AWS_S3_CUSTOM_DOMAIN="public.example.org"
    )
    def test_r2_signing_does_not_inherit_aws_session_token_or_custom_domain(self):
        url = urlsplit(self.storage().url("test.pdf"))
        self.assertEqual(url.hostname, "account.r2.cloudflarestorage.com")
        self.assertNotIn("X-Amz-Security-Token", parse_qs(url.query))

    def test_unmapped_buckets_keep_signed_s3_urls(self):
        query_url = urlsplit(self.storage(bucket="other-bucket").url("test.pdf"))
        self.assertIn("amazonaws.com", query_url.hostname)
        self.assertEqual(
            parse_qs(query_url.query)["X-Amz-Credential"][0].split("/")[0], "s3-key"
        )

    @override_settings(R2_ENDPOINT_URL="", R2_ACCESS_KEY_ID="", R2_SECRET_ACCESS_KEY="")
    def test_downloads_stay_on_s3_until_r2_endpoint_is_configured(self):
        self.assertIn(
            "amazonaws.com", urlsplit(self.storage().url("test.pdf")).hostname
        )

    def test_configured_endpoint_requires_both_r2_credentials(self):
        for setting in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            with self.subTest(setting=setting), override_settings(**{setting: ""}):
                with self.assertRaisesMessage(
                    ImproperlyConfigured, "R2 downloads require"
                ):
                    self.storage().url("test.pdf")

    def test_file_operations_use_s3_even_after_signing_an_r2_url(self):
        for klass in (S3Storage, DynamicS3Boto3Storage):
            with self.subTest(storage=klass):
                storage = self.storage(klass)
                storage.url("test.pdf")
                self.assertEqual(storage.bucket.name, "primary-bucket")
                obj = Mock()
                obj.download_fileobj.side_effect = lambda file, **kwargs: file.write(
                    b"original"
                )
                with patch.object(
                    storage.bucket, "Object", return_value=obj
                ) as get_object:
                    saved = storage.save("test.pdf", ContentFile(b"original"))
                    self.assertEqual(
                        saved,
                        "s3:primary-bucket:test.pdf"
                        if klass is DynamicS3Boto3Storage
                        else "test.pdf",
                    )
                    obj.upload_fileobj.assert_called_once()
                    with storage.open("test.pdf", "rb") as file:
                        self.assertEqual(file.read(), b"original")
                    obj.load.assert_called_once()
                    obj.download_fileobj.assert_called_once()
                    storage.delete("test.pdf")
                    obj.delete.assert_called_once()
                    self.assertTrue(
                        all(
                            call.args == ("test.pdf",)
                            for call in get_object.call_args_list
                        )
                    )

    def test_source_filename_metadata_is_updated_on_s3(self):
        storage = self.storage()
        storage.url("test.pdf")
        source = SimpleNamespace(
            source_url=None,
            file=SimpleNamespace(storage=storage, name="test.pdf"),
            filename_for_download=lambda: "document.pdf",
        )
        with patch.object(storage.connection.meta.client, "copy_object") as copy:
            SourceFile.set_download_filename(source)
        self.assertEqual(copy.call_args.kwargs["Bucket"], "primary-bucket")
        self.assertEqual(
            copy.call_args.kwargs["CopySource"],
            {"Bucket": "primary-bucket", "Key": "test.pdf"},
        )

    def test_document_redirect_keeps_browser_private_cache_policy(self):
        storage = self.storage()
        response = DocumentSourcePDFView().redirect_to_storage(
            SimpleNamespace(url=storage.url("test.pdf"))
        )
        self.assertEqual(
            urlsplit(response["Location"]).hostname, "account.r2.cloudflarestorage.com"
        )
        self.assertEqual(
            set(response["Cache-Control"].split(", ")),
            {"private", "max-age=240", "must-revalidate"},
        )

    @override_settings(R2_DOWNLOAD_BUCKETS={"primary-bucket": "mirror-bucket"})
    def test_dynamic_fields_keep_the_s3_database_name(self):
        source = SourceFile(file="s3:primary-bucket:media/test.pdf")
        self.assertIsInstance(source.file.storage, S3Boto3Storage)
        self.assertEqual(source.file.storage.bucket_name, "primary-bucket")
        self.assertEqual(source.file.name, "media/test.pdf")
        source.file.storage.access_key = "s3-key"
        source.file.storage.secret_key = "s3-secret"
        self.assertIn("/mirror-bucket/media/test.pdf", source.file.url)
