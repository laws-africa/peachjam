from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.core.files.base import ContentFile
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from storages.backends.s3boto3 import S3Boto3Storage

from peachjam.storage import DynamicS3Boto3Storage
from peachjam.views.article import ArticleAttachmentDetailView
from peachjam.views.documents import (
    DocumentAttachmentView,
    DocumentMediaView,
    DocumentPublicationView,
    DocumentSocialImageView,
    DocumentSourcePDFView,
    DocumentSourceView,
)
from peachjam.views.media import PublicImageView
from peachjam.views.partner import PartnerLogoView


@override_settings(DYNAMIC_STORAGE={"PREFIXES": {"s3": {}}})
class SignedDownloadTestCase(SimpleTestCase):
    def assert_private_redirect_cache(self, response):
        self.assertEqual(
            set(response["Cache-Control"].split(", ")),
            {"private", "max-age=240", "must-revalidate"},
        )

    def test_page_and_site_cache_middleware_preserve_private_redirect_policy(self):
        from django.views.decorators.cache import cache_page

        from peachjam.middleware import GeneralUpdateCacheMiddleware

        request = RequestFactory().get("/akn/test/source.pdf")
        view = self.view(DocumentSourcePDFView)
        endpoint = cache_page(86400)(lambda request: view.render_to_response({}))
        response = endpoint(request)
        response = GeneralUpdateCacheMiddleware(
            lambda request: response
        ).process_response(request, response)
        self.assert_private_redirect_cache(response)

    def test_redirect_cache_lifetime_tracks_signature_expiry(self):
        for expiry, expected_max_age in ((600, 540), (60, 0), (30, 0)):
            with (
                self.subTest(expiry=expiry),
                override_settings(AWS_QUERYSTRING_EXPIRE=expiry),
            ):
                view = self.view(DocumentSourcePDFView)
                response = view.render_to_response({})
                self.assertEqual(
                    parse_qs(urlsplit(response["Location"]).query)["X-Amz-Expires"],
                    [str(expiry)],
                )
                self.assertEqual(
                    set(response["Cache-Control"].split(", ")),
                    {"private", f"max-age={expected_max_age}", "must-revalidate"},
                )

    def storage(self, endpoint="https://account.r2.cloudflarestorage.com"):
        return DynamicS3Boto3Storage(
            name="s3:documents:test.txt",
            access_key="test-key",
            secret_key="test-secret",
            endpoint_url=endpoint,
            region_name="auto",
            signature_version="s3v4",
        )

    def test_urls_are_signed_for_five_minutes_without_custom_domain(self):
        for endpoint in (
            "https://account.r2.cloudflarestorage.com",
            "https://s3.eu-west-1.amazonaws.com",
        ):
            with self.subTest(endpoint=endpoint):
                url = urlsplit(self.storage(endpoint).url("test.txt"))
                self.assertNotEqual(url.hostname, "public.example.com")
                query = parse_qs(url.query)
                self.assertEqual(query["X-Amz-Expires"], ["300"])
                self.assertEqual(query["X-Amz-Algorithm"], ["AWS4-HMAC-SHA256"])
                self.assertTrue(query["X-Amz-Signature"])

    def view(self, view_class, anonymised=False, source_url=None):
        file = ContentFile(b"safe content", name="test.txt")
        file.storage = self.storage()
        # Use a mock file so accessing url never opens or downloads the object.
        remote_file = Mock(storage=file.storage, url=file.storage.url(file.name))
        remote_file.open.return_value = file
        remote_file.read.return_value = b"safe content"
        source = SimpleNamespace(
            file=remote_file,
            mimetype="text/plain",
            source_url=source_url,
            file_is_anonymised=True,
            anonymised_file_as_pdf=None,
            as_pdf=lambda: remote_file,
            filename_for_download=lambda *args: "safe.txt",
        )
        view = view_class()
        view.object = SimpleNamespace(source_file=source, anonymised=anonymised)
        return view

    def test_source_and_pdf_redirects_are_privately_cacheable(self):
        for view_class in (DocumentSourceView, DocumentSourcePDFView):
            with self.subTest(view=view_class):
                view = self.view(view_class)
                response = view.render_to_response({})
                self.assertEqual(response.status_code, 302)
                self.assertIn("X-Amz-Signature=", response["Location"])
                self.assert_private_redirect_cache(response)
                view.object.source_file.file.open.assert_not_called()

    def test_standard_s3_storage_redirects_are_privately_cacheable(self):
        for view_class in (DocumentSourceView, DocumentSourcePDFView):
            with self.subTest(view=view_class):
                view = self.view(view_class)
                view.object.source_file.file.storage = S3Boto3Storage(
                    access_key="test-key", secret_key="test-secret"
                )
                response = view.render_to_response({})
                self.assertEqual(response.status_code, 302)
                self.assertIn("X-Amz-Signature=", response["Location"])
                self.assert_private_redirect_cache(response)
                view.object.source_file.file.open.assert_not_called()

    def test_source_url_redirects_are_unchanged(self):
        for view_class in (DocumentSourceView, DocumentSourcePDFView):
            view = self.view(view_class, source_url="https://example.com/original")
            view.object.source_file.mimetype = (
                "application/pdf"
                if view_class == DocumentSourcePDFView
                else "text/plain"
            )
            response = view.render_to_response({})
            self.assertEqual(response["Location"], "https://example.com/original")
            self.assertNotIn("Cache-Control", response)

    def test_anonymised_files_still_stream(self):
        for view_class in (DocumentSourceView, DocumentSourcePDFView):
            view = self.view(
                view_class, anonymised=True, source_url="https://example.com/original"
            )
            response = view.render_to_response({})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"safe content")
            self.assertNotIn("Location", response)

    def test_default_s3_storage_signs_without_custom_domain(self):
        storage = S3Boto3Storage(
            bucket_name="documents",
            access_key="test-key",
            secret_key="test-secret",
            signature_version="s3v4",
            region_name="eu-west-1",
        )
        url = urlsplit(storage.url("test.png"))
        self.assertNotEqual(url.hostname, "public.example.com")
        self.assertEqual(parse_qs(url.query)["X-Amz-Expires"], ["300"])
        self.assertIn("X-Amz-Signature", parse_qs(url.query))

    def test_remaining_document_downloads_redirect_without_opening_storage(self):
        file = self.view(DocumentSourceView).object.source_file.file
        attachment = SimpleNamespace(file=file, private=False)
        for view_class in (
            DocumentMediaView,
            DocumentAttachmentView,
            DocumentPublicationView,
            DocumentSocialImageView,
        ):
            with self.subTest(view=view_class):
                view = view_class()
                view.kwargs = {"filename": "test.png"}
                view.object = Mock()
                view.object.attachedfiles_set.filter.return_value.first.return_value = (
                    attachment
                )
                view.object.publication_file = SimpleNamespace(
                    file=file, use_source_file=False, url=None
                )
                with (
                    patch(
                        "peachjam.views.documents.get_list_or_404",
                        return_value=[attachment],
                    ),
                    patch.object(view, "get_object", return_value=view.object),
                    patch(
                        "peachjam.views.documents.DocumentSocialImage.html_for_document"
                    ),
                    patch(
                        "peachjam.views.documents.DocumentSocialImage.get_or_create_for_document",
                        return_value=attachment,
                    ),
                ):
                    response = (
                        view.get(RequestFactory().get("/image"))
                        if view_class == DocumentSocialImageView
                        else view.render_to_response({})
                    )
                self.assertEqual(response.status_code, 302)
                self.assertIn("X-Amz-Signature=", response["Location"])
                self.assert_private_redirect_cache(response)
                file.open.assert_not_called()

    def test_private_attachment_cannot_issue_signed_url(self):
        view = DocumentAttachmentView()
        view.kwargs = {"filename": "private.pdf"}
        view.object = Mock()
        view.object.attachedfiles_set.filter.return_value.first.return_value = (
            SimpleNamespace(private=True)
        )
        with self.assertRaises(Http404):
            view.render_to_response({})

    def test_public_images_articles_and_logos_stream(self):
        for view_class in (
            PublicImageView,
            ArticleAttachmentDetailView,
            PartnerLogoView,
        ):
            with self.subTest(view=view_class):
                view = view_class()
                view.object = SimpleNamespace(
                    file=ContentFile(b"public content", name="image.png"),
                    filename="image.png",
                )
                if view_class == PublicImageView:
                    view.field_name = "file"
                response = view.render_to_response({})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    b"".join(response.streaming_content), b"public content"
                )
                self.assertNotIn("Location", response)
                response.close()


class PublicImageURLTestCase(SimpleTestCase):
    def test_templates_use_stable_image_urls(self):
        from django.template.loader import render_to_string
        from django.urls import reverse

        image = Mock()
        image.url = "https://public.example.com/unsigned.png"
        article = SimpleNamespace(
            pk=123,
            image=image,
            get_absolute_url=lambda: "/articles/test",
            title="Test article",
            summary="Test",
            date=None,
            author=SimpleNamespace(username="author", first_name="", last_name=""),
            topics=SimpleNamespace(all=[]),
        )
        html = render_to_string("peachjam/article/_list.html", {"articles": [article]})
        self.assertIn(reverse("article_image", args=[123]), html)
        self.assertNotIn("public.example.com", html)


class PublicImageAccessTestCase(TestCase):
    def test_article_image_requires_a_published_article(self):
        from django.contrib.auth.models import User
        from django.db.models.fields.files import FieldFile
        from django.urls import reverse

        from peachjam.models import Article

        author = User.objects.create(username="image-author")
        article = Article.objects.create(
            pk=987654,
            author=author,
            title="Test",
            slug="test",
            date="2026-11-21",
            image="articles/test.png",
            published=False,
        )
        url = reverse("article_image", args=[article.pk])
        with patch.object(
            FieldFile, "open", return_value=ContentFile(b"image", name="image.png")
        ) as open_file:
            self.assertEqual(self.client.get(url).status_code, 404)
            open_file.assert_not_called()
            article.published = True
            article.save()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"image")
            response.close()
