import logging
import os
import re

import magic
from django.core.files import File
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from docpipe.soffice import soffice_convert

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

    def save(self, *args, **kwargs):
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
