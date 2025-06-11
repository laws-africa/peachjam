from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from lxml import etree
from polymorphic.models import PolymorphicModel


class ProvisionEnrichment(PolymorphicModel):
    # TODO: add more choices
    ENRICHMENT_TYPE_CHOICES = (
        ("provision_enrichment", _("Provision enrichment")),
        ("unconstitutional_provision", _("Unconstitutional provision")),
        ("uncommenced_provision", _("Uncommenced provision")),
    )

    work = models.ForeignKey(
        "peachjam.Work",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        related_name="enrichments",
        verbose_name=_("work"),
    )
    provision_eid = models.CharField(
        _("provision eid"), max_length=2048, null=True, blank=True
    )
    whole_work = models.BooleanField(_("whole work"), default=False)
    enrichment_type = models.CharField(
        _("enrichment type"),
        max_length=256,
        choices=ENRICHMENT_TYPE_CHOICES,
        default="provision_enrichment",
        null=False,
        blank=False,
    )
    text = models.CharField(_("text"), max_length=2048, null=True, blank=True)

    # this is the document that will be used to display provision information
    _document = None

    class Meta:
        verbose_name = _("provision enrichment")
        verbose_name_plural = _("provision enrichments")

    def __str__(self):
        return f"{self.enrichment_type} - {self.work} - {self.provision_eid or 'whole work'}"

    @property
    def document(self):
        if self._document is None:
            self._document = self.work.documents.latest_expression().first()
        return self._document

    @document.setter
    def document(self, value):
        self._document = value

    @cached_property
    def provision_by_eid(self):
        html_content = self.document.content_html
        if not html_content:
            return None
        parser = etree.HTMLParser()
        tree = etree.fromstring(html_content, parser)

        # Find element with data-eId
        xpath = f"//*[@data-eid='{self.provision_eid}']"
        elements = tree.xpath(xpath)

        if elements:
            return etree.tostring(elements[0], encoding="unicode", method="html")
        return None

    @cached_property
    def provision_title(self):
        """A friendly title for this provision, if available."""
        if self.provision_eid:
            return self.document.friendly_provision_title(self.provision_eid)

    def save(self, *args, **kwargs):
        if not self.provision_eid:
            self.whole_work = True
        if self.whole_work:
            self.provision_eid = None
        super().save(*args, **kwargs)


class UnconstitutionalProvision(ProvisionEnrichment):
    judgment = models.ForeignKey(
        "peachjam.Work",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="provisions_deemed_unconstitutional",
        verbose_name=_("judgment"),
    )
    date_deemed_unconstitutional = models.DateField(
        _("date deemed unconstitutional"), null=True, blank=True
    )
    end_of_suspension_period = models.DateField(
        _("end of suspension period"), null=True, blank=True
    )
    resolved = models.BooleanField(_("resolved"), default=False)
    date_resolved = models.DateField(_("date resolved"), null=True, blank=True)
    resolving_amendment_work = models.ForeignKey(
        "peachjam.Work",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="unconstitutional_provisions_resolved",
        verbose_name=_("resolving amendment work"),
    )

    class Meta:
        verbose_name = _("unconstitutional provision")
        verbose_name_plural = _("unconstitutional provisions")

    def save(self, *args, **kwargs):
        self.enrichment_type = "unconstitutional_provision"
        super().save(*args, **kwargs)


class UncommencedProvision(ProvisionEnrichment):
    and_all_descendants = models.BooleanField(_("and all descendants"), default=False)

    class Meta:
        verbose_name = _("uncommenced provision")
        verbose_name_plural = _("uncommenced provisions")

    def save(self, *args, **kwargs):
        self.enrichment_type = "uncommenced_provision"
        super().save(*args, **kwargs)
