from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils.module_loading import import_string
from storages.backends.s3boto3 import S3Boto3Storage

""" Support for storing file fields in different storages. This lets us store and work with content
in different S3 buckets.

The filename stored in the database includes the name of a storage mechanism and extra storage
data (eg. the S3 bucket name), if any. For example:

  s3:my-bucket:path/to/object.pdf

Django storages doesn't make this easy. When the field is declared, django expects to be able
to load one storage for all objects using that field. Instead, we intervene at two points to
customise the storage being loaded: when first accessing the file backing the field, and when
saving the field to the database.

In both instances, the prefix information is stripped and a suitable storage constructed from it.
When the file is saved to the db, the prefix information is re-added.
"""


def get_dynamic_storage(field, model_instance, name=None):
    """Return an instance of a storage class for this field and model."""
    # only use if configured
    if not getattr(settings, "DYNAMIC_STORAGE", None):
        return default_storage

    # the 'name or' protects against infinite recursion, because we can't get the data field
    # off the model_instance without it creating an instance of the FieldFile class, which will
    # call this again, etc.
    name = name or getattr(model_instance, field.attname).name
    assert name

    if ":" not in name:
        name = get_default_storage_prefix(field, model_instance, name) + name

    prefix, _ = name.split(":", 1)
    config = settings.DYNAMIC_STORAGE["PREFIXES"].get(prefix)
    if not config:
        raise ValueError(
            f"No configuration for prefix {prefix} in settings.DYNAMIC_STORAGE['PREFIXES']"
        )

    klass = import_string(config["storage"])
    kwargs = config.get("storage_kwargs", {})
    return klass(name=name, **kwargs)


def get_default_storage_prefix(field, model_instance, name):
    """Get the prefix to use by default when one hasn't been specified. This is done by looking up
    the prefix to use in settings.DYNAMIC_STORAGE["DEFAULTS"] using the fully-qualified class name
    of the model instance. If none is specified it falls back to looking up the default for
    the empty string.
    """
    prefix = settings.DYNAMIC_STORAGE["DEFAULTS"][""]
    klass = model_instance.__class__
    lookup = klass.__module__ + "." + klass.__qualname__
    return settings.DYNAMIC_STORAGE["DEFAULTS"].get(lookup, prefix)


class DynamicStorageFieldFile(FieldFile):
    """File matching the dynamic file field below, which dynamically configures its own storage."""

    def __init__(self, instance, field, name):
        super().__init__(instance, field, name)

        if getattr(field, "get_storage", None):
            self.storage = field.get_storage(instance, name)
            if hasattr(self.storage, "unformat_name"):
                # the storage has extracted all that it needs, we can strip the metadata
                self.name = self.storage.unformat_name(name)


class DynamicStorageFileField(models.FileField):
    """File field for models that dynamically looks up the storage to use for the field."""

    attr_class = DynamicStorageFieldFile
    get_storage = get_dynamic_storage

    def __init__(self, *args, **kwargs):
        if kwargs.get("get_storage"):
            self.get_storage = kwargs["get_storage"]
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        if self.get_storage:
            self.storage = self.get_storage(model_instance)
        return super().pre_save(model_instance, add)


class DynamicStorageMixin:
    """Mixin for make a storage dynamic. Ensures that the storage is used for its configured prefix, and adds/removes
    the prefix information from the file name when necessary.
    """

    prefix = None

    def __init__(self, name, *args, **kwargs):
        prefix, rest = name.split(":", 1)
        assert prefix == self.prefix
        config = self.get_dynamic_storage_config(rest, *args, **kwargs)
        kwargs.update(config)
        super().__init__(*args, **kwargs)

    def get_dynamic_storage_config(self, name, *args, **kwargs):
        return {}

    def _save(self, name, content):
        # after saving, format the name so it has all the details
        return self.format_name(super()._save(name, content))

    def format_name(self, name):
        """Add prefix information to the name."""
        if not name.startswith(self.prefix + ":"):
            return f"{self.prefix}:{name}"

    def unformat_name(self, name):
        """Remove prefix information from the name."""
        if name.startswith(self.prefix + ":"):
            return name.split(":", 1)[-1]
        return name


class DynamicFileSystemStorage(DynamicStorageMixin, FileSystemStorage):
    prefix = "file"


class DynamicS3Boto3Storage(DynamicStorageMixin, S3Boto3Storage):
    """S3 storage that knows how to add and strip the bucket prefix from the filename.

    Additionally, if silent_readonly is set, then this storage will silently discard
    write operations.
    """

    prefix = "s3"

    def get_dynamic_storage_config(self, info, *args, **kwargs):
        bucket = info.split(":", 1)[0]
        config = super().get_dynamic_storage_config(info, *args, **kwargs)
        config.update(
            settings.DYNAMIC_STORAGE["PREFIXES"][self.prefix]
            .get("buckets", {})
            .get(bucket, {})
        )
        config["bucket_name"] = bucket
        self.silent_readonly = config.pop("silent_readonly", False)
        return config

    def _save(self, name, content):
        if self.silent_readonly:
            # no-op if readonly
            return self.format_name(self._clean_name(name))
        return super()._save(name, content)

    def delete(self, name):
        # no-op if readonly
        if not self.silent_readonly:
            super().delete(name)

    def format_name(self, name):
        if not name.startswith(self.prefix + ":"):
            return f"{self.prefix}:{self.bucket_name}:{name}"

    def unformat_name(self, name):
        if name.startswith(self.prefix + ":"):
            return name.split(":", 2)[-1]
        return name
