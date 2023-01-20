from django.db import models
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        pass

    def save(self, *args, **kwargs):
        self.pk = 1
        super(BaseModel, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


class PeachJamSettings(BaseModel):
    default_document_language = models.ForeignKey(
        "languages_plus.Language",
        related_name="+",
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_("default document language"),
    )
    document_languages = models.ManyToManyField(
        "languages_plus.Language",
        related_name="+",
        blank=True,
        verbose_name=_("document languages"),
    )
    document_jurisdictions = models.ManyToManyField(
        "countries_plus.Country",
        related_name="+",
        blank=True,
        verbose_name=_("document jurisdictions"),
    )
    subleg_label = models.CharField(
        verbose_name=_("subsidiary legislation label"),
        max_length=1024,
        default="Subsidiary legislation",
    )

    class Meta:
        verbose_name = verbose_name_plural = _("site settings")

    def __str__(self):
        return "Settings"


def pj_settings():
    return PeachJamSettings.load()
