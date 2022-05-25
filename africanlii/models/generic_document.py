from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse

from peachjam.models import CoreDocument


class AuthoringBody(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(default="", editable=False, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Authoring bodies"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("author_list", kwargs={"slug": self.slug, "pk": str(self.id)})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


class DocumentNature(models.Model):
    name = models.CharField(max_length=1024, null=False, blank=False, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class GenericDocument(CoreDocument):
    authoring_body = models.ForeignKey(
        AuthoringBody, on_delete=models.PROTECT, null=False, blank=False
    )
    nature = models.ForeignKey(
        DocumentNature, on_delete=models.PROTECT, null=False, blank=False
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "generic_document"
        return super().save(*args, **kwargs)


class LegalInstrument(CoreDocument):
    authoring_body = models.ForeignKey(
        AuthoringBody, on_delete=models.PROTECT, null=False, blank=False
    )
    nature = models.ForeignKey(
        DocumentNature, on_delete=models.PROTECT, null=False, blank=False
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "legal_instrument"
        return super().save(*args, **kwargs)


class Legislation(CoreDocument):
    metadata_json = models.JSONField(null=False, blank=False)

    class Meta:
        verbose_name_plural = "Legislation"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.doc_type = "legislation"
        return super().save(*args, **kwargs)
