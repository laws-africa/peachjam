from django.db import models
from django.db.models.fields.files import FieldFile
from storages.backends.s3boto3 import S3Boto3Storage


class DynamicStorageFieldFile(FieldFile):
    def __init__(self, instance, field, name):
        super().__init__(instance, field, name)
        # TODO: don't use this storage mechanism in debug mode
        # TODO: default?
        bucket = name.split("/", 1)[0]
        self.storage = S3Boto3Storage(bucket_name=bucket)


class DynamicStorageFileField(models.FileField):
    attr_class = DynamicStorageFieldFile

    def pre_save(self, model_instance, add):
        # TODO: get bucket
        filename = getattr(model_instance, self.attname)
        bucket = filename.split("/", 1)[0]
        # TODO: don't use this storage mechanism in debug mode
        self.storage = S3Boto3Storage(bucket_name=bucket)
        return super().pre_save(model_instance, add)
