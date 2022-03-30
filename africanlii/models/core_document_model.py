import os
from django.db import models
from django.core import serializers
from django.contrib.contenttypes.fields import GenericRelation, GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from languages_plus.models import Language
from countries_plus.models import Country


class Locality(models.Model):
    name = models.CharField(max_length=255, null=False)
    jurisdiction = models.ForeignKey(Country, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = 'localities'
        ordering = ['name']
        unique_together = ['name', 'jurisdiction']

    def __str__(self):
        return f'{self.name}'


def image_location(instance, filename):
    return f'media/images/{instance.content_type.name}/{instance.object_id}/{os.path.basename(filename)}'


class Image(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    file = models.ImageField(upload_to=image_location)
    filename = models.CharField(max_length=1024, null=False)
    mimetype = models.CharField(max_length=1024, null=False)


def source_file_location(instance, filename):
    if instance.pk is not None:
        return f'media/source_files/{instance.pk}/{os.path.basename(filename)}'
    1 / 0

class SourceFile(models.Model):
    file = models.FileField(upload_to=source_file_location)
    filename = models.CharField(max_length=1024, null=False)
    mimetype = models.CharField(max_length=1024, null=False)


class CoreDocumentModel(models.Model):
    """
    This is the abstract document model that has fields that are
    common to most documents.
    """
    title = models.CharField(max_length=1024, null=False, blank=False)
    date = models.DateField(null=False, blank=False)
    source_url = models.URLField(max_length=2048, null=True, blank=True)
    source_file = models.OneToOneField(SourceFile, on_delete=models.PROTECT)
    citation = models.CharField(max_length=1024, null=True, blank=True)
    content_html = models.TextField(null=True, blank=True)
    images = GenericRelation(Image)
    language = models.ForeignKey(Language, on_delete=models.PROTECT, null=False, blank=False)
    jurisdiction = models.ForeignKey(Country, on_delete=models.PROTECT, null=False, blank=False)
    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, null=True, blank=True)
    expression_frbr_uri = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    work_frbr_uri = models.CharField(max_length=1024, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['title']

    def get_all_fields(self):
        return self._meta.get_fields()

    def get_all_values(self):
        return serializers.serialize('python', [self])[0]['fields']
