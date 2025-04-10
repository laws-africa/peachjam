import base64
import hashlib
import io
import logging
import os
import re

import magic
from django.contrib.staticfiles.finders import find as find_static
from django.core.files import File
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from docpipe.soffice import soffice_convert

from peachjam.helpers import html_to_png
from peachjam.storage import DynamicStorageFileField

log = logging.getLogger(__name__)


def file_location(instance, filename):
    if not instance.document.pk:
        raise ValueError("Document must be saved before file can be attached")
    doc_type = instance.document.doc_type
    pk = instance.document.pk
    folder = instance.SAVE_FOLDER
    filename = os.path.basename(filename)
    # generate a random nonce so that we never re-use an existing filename, so that we can guarantee that
    # we don't overwrite it (which makes it easier to cache files)
    nonce = os.urandom(8).hex()
    return f"media/{doc_type}/{pk}/{folder}/{nonce}/{filename}"


class AttachmentAbstractModel(models.Model):
    filename = models.CharField(_("filename"), max_length=1024, null=False, blank=False)
    mimetype = models.CharField(_("mimetype"), max_length=1024, null=False, blank=False)
    size = models.BigIntegerField(_("size"), default=0)
    file = DynamicStorageFileField(_("file"), upload_to=file_location, max_length=1024)

    def __str__(self):
        return f"{self.filename}"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.filename:
            self.filename = self.file.name
        if not self.size:
            self.size = self.file.size
        if not self.mimetype:
            self.file.seek(0)
            self.mimetype = magic.from_buffer(self.file.read(), mime=True)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.file:
            try:
                self.file.delete(False)
            except Exception as e:
                log.warning(f"Ignoring error while deleting {self.file}", exc_info=e)
        return super().delete(*args, **kwargs)


class Image(AttachmentAbstractModel):
    SAVE_FOLDER = "images"

    document = models.ForeignKey(
        "peachjam.CoreDocument",
        related_name="images",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    file = models.ImageField(_("file"), upload_to=file_location, max_length=1024)

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")
        unique_together = ("document", "filename")

    @classmethod
    def from_docpipe_attachment(cls, attachment):
        f = File(attachment.file, name=attachment.filename)
        return Image(
            filename=attachment.filename,
            mimetype=attachment.content_type,
            size=f.size,
            file=f,
        )


class SourceFile(AttachmentAbstractModel):
    SAVE_FOLDER = "source_file"

    document = models.OneToOneField(
        "peachjam.CoreDocument",
        related_name="source_file",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    source_url = models.URLField(
        _("source URL"), max_length=2048, null=True, blank=True
    )
    file_as_pdf = models.FileField(
        _("file as pdf"),
        upload_to=file_location,
        max_length=1024,
        null=True,
        blank=True,
    )
    sha256 = models.CharField(
        "SHA 256", max_length=64, null=True, blank=True, db_index=True
    )

    class Meta:
        verbose_name = _("source file")
        verbose_name_plural = _("source files")

    def as_pdf(self):
        if self.mimetype == "application/pdf":
            return self.file
        elif self.file_as_pdf:
            return self.file_as_pdf
        else:
            return None

    def convert_to_pdf(self):
        if self.mimetype != "application/pdf" and not self.file_as_pdf:
            suffix = os.path.splitext(self.filename)[1].replace(".", "")
            pdf = soffice_convert(self.file, suffix, "pdf")[0]
            self.file_as_pdf = File(pdf, name=f"{self.file.name[:-5]}.pdf")
            self.save()

    def ensure_file_as_pdf(self):
        from peachjam.tasks import convert_source_file_to_pdf

        if self.mimetype != "application/pdf" and not self.file_as_pdf:
            convert_source_file_to_pdf(self.id, creator=self.document)

    def filename_extension(self):
        return os.path.splitext(self.filename)[1][1:]

    def filename_for_download(self, ext=None):
        """Return a generated filename appropriate for use when downloading this source file."""
        ext = ext or os.path.splitext(self.filename)[1]
        title = re.sub(r"[^a-zA-Z0-9() ]", "", self.document.title)
        return title + ext

    def set_download_filename(self):
        """For S3-backed storages, set the content-disposition header to a filename suitable for download. This is
        only when serving the file from S3 or some other CDN backed by S3 (including CloudFront and CloudFlare)."""
        if not self.source_url and getattr(self.file.storage, "bucket_name", None):
            metadata = self.file.storage.get_object_parameters(self.file.name)
            metadata[
                "ContentDisposition"
            ] = f'attachment; filename="{self.filename_for_download()}"'
            src = {"Bucket": self.file.storage.bucket_name, "Key": self.file.name}
            self.file.storage.connection.meta.client.copy_object(
                CopySource=src, MetadataDirective="REPLACE", **src, **metadata
            )

    def calculate_sha256(self):
        self.sha256 = hashlib.sha256(self.file.read()).hexdigest()

    def save(self, *args, **kwargs):
        if not self.sha256:
            self.calculate_sha256()
        pk = self.pk
        super().save(*args, **kwargs)
        if not pk:
            # first save, set the download filename
            self.set_download_filename()


class PublicationFile(AttachmentAbstractModel):
    SAVE_FOLDER = "publication_file"

    file = models.FileField(
        _("file"), upload_to=file_location, max_length=1024, blank=True, null=True
    )
    document = models.OneToOneField(
        "peachjam.CoreDocument",
        related_name="publication_file",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    url = models.URLField(
        _("URL"),
        max_length=2048,
        null=True,
        blank=True,
        help_text=_("The external URL (e.g. on gazettes.africa) where this file lives"),
    )
    use_source_file = models.BooleanField(
        _("use source file"),
        default=False,
        help_text=_(
            "Set to True if the source file on the same document can be used instead"
        ),
    )

    class Meta:
        verbose_name = _("publication file")
        verbose_name_plural = _("publication files")

    def filename_extension(self):
        return os.path.splitext(self.filename)[1][1:]


class AttachedFileNature(models.Model):
    name = models.CharField(
        _("name"), max_length=1024, null=False, blank=False, unique=True
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("attached file nature")
        verbose_name_plural = _("attached file natures")

    def __str__(self):
        return self.name


class AttachedFiles(AttachmentAbstractModel):
    SAVE_FOLDER = "attachments"

    document = models.ForeignKey(
        "peachjam.CoreDocument", on_delete=models.CASCADE, verbose_name=_("document")
    )
    nature = models.ForeignKey(
        AttachedFileNature, on_delete=models.CASCADE, verbose_name=_("nature")
    )

    class Meta:
        verbose_name = _("attached file")
        verbose_name_plural = _("attached files")

    def extension(self):
        return os.path.splitext(self.filename)[1].replace(".", "")


class ArticleAttachment(AttachmentAbstractModel):
    SAVE_FOLDER = "attachments"
    document = models.ForeignKey(
        "peachjam.Article", on_delete=models.CASCADE, related_name="attachments"
    )

    def __str__(self):
        return self.file.name

    def get_absolute_url(self):
        return reverse(
            "article_attachment",
            kwargs={
                "date": self.document.date.strftime("%Y-%m-%d"),
                "author": self.document.author.username,
                "slug": self.document.slug,
                "pk": self.pk,
                "filename": self.filename,
            },
        )


class DocumentSocialImage(models.Model):
    SAVE_FOLDER = "social-images"
    template_name = "peachjam/document/social_image.html"

    document = models.OneToOneField(
        "peachjam.CoreDocument",
        related_name="social_media_image",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    file = models.FileField(_("file"), upload_to=file_location, max_length=1024)
    html_md5sum = models.CharField(
        _("html md5sum"), max_length=32, null=True, blank=True
    )
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("social media image")
        verbose_name_plural = _("social media images")

    def delete(self, *args, **kwargs):
        self.delete_file()
        return super().delete(*args, **kwargs)

    def delete_file(self):
        """Delete the file, if present, and silently ignore errors."""
        if self.file:
            try:
                self.file.delete(False)
            except Exception as e:
                log.warning(f"Ignoring error while deleting {self.file}", exc_info=e)

    @classmethod
    def get_or_create_for_document(cls, document, html_str):
        image = cls.objects.filter(document=document).first()

        # has the html changed?
        html_md5sum = hashlib.md5(html_str.encode()).hexdigest()
        if image and html_md5sum == image.html_md5sum:
            return image

        # render the html into an image using puppeteer and chrome
        f = File(io.BytesIO(cls.make_image(html_str)), name="social-image.png")
        image, created = cls.objects.update_or_create(
            document=document, defaults={"file": f, "html_md5sum": html_md5sum}
        )
        return image

    @classmethod
    def html_for_document(cls, document, debug=False):
        context = {
            "document": document,
            "debug": debug,
        }

        # find the logo to use and inject it as base 64
        for fname in ["images/hero-logo.jpg", "images/logo.png"]:
            fname = find_static(fname)
            if fname:
                with open(fname, "rb") as f:
                    file_content = f.read()
                    base64_encoded = base64.b64encode(file_content).decode("utf-8")
                    context["logo_b64"] = f"data:image/jpg;base64,{base64_encoded}"
                    break

        return render_to_string(cls.template_name, context)

    @classmethod
    def make_image(cls, html_str):
        return html_to_png(html_str, "1200x600")
