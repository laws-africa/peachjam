import os

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from peachjam.models import AttachmentAbstractModel


def file_location(instance, filename):
    assert instance.partner.pk is not None
    filename = os.path.basename(filename)
    # generate a random nonce so that we never re-use an existing filename, so that we can guarantee that
    # we don't overwrite it (which makes it easier to cache files)
    nonce = os.urandom(8).hex()
    return f"partners/{instance.partner.pk}/{nonce}/{filename}"


class Partner(models.Model):
    name = models.CharField(_("name"), max_length=255, unique=True)
    url = models.URLField(_("url"), blank=True, null=True)
    document_blurb_html = models.TextField(_("document blurb"), blank=True, null=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "partner"
        verbose_name_plural = "partners"

    def __str__(self):
        return self.name


class PartnerLogo(AttachmentAbstractModel):
    partner = models.OneToOneField(
        Partner,
        related_name="logo",
        on_delete=models.CASCADE,
        verbose_name=_("partner"),
    )
    file = models.ImageField(_("file"), upload_to=file_location, max_length=1024)

    class Meta:
        verbose_name = _("logo")
        verbose_name_plural = _("logos")

    def get_absolute_url(self):
        return reverse("partner_logo", args=[self.partner.pk, self.pk])
