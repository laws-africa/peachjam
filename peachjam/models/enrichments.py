from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel


class ProvisionEnrichment(PolymorphicModel):
    # TODO: add more choices
    ENRICHMENT_TYPE_CHOICES = (
        ("provision_enrichment", _("Provision enrichment")),
        ("unconstitutional_provision", _("Unconstitutional provision")),
        ("uncommenced_provision", _("Uncommenced provision")),
        ("provision_citation", _("Provision citation")),
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
    text = models.CharField(_("text"), max_length=4096, null=True, blank=True)

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
        return self.document.get_provision_by_eid(self.provision_eid)

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
    read_in_text_html = models.CharField(
        _("read-in text HTML"), max_length=4096, null=True, blank=True
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


class ProvisionCitation(ProvisionEnrichment):
    prefix = models.CharField(_("prefix"), max_length=1024, null=True, blank=True)
    suffix = models.CharField(_("suffix"), max_length=1024, null=True, blank=True)
    exact = models.CharField(_("exact"), max_length=1024, null=True, blank=True)
    citing_document = models.ForeignKey(
        "peachjam.CoreDocument",
        on_delete=models.CASCADE,
        related_name="provision_citations",
        verbose_name=_("citing document"),
    )

    class Meta:
        verbose_name = _("provision citation")
        verbose_name_plural = _("provision citations")

    def save(self, *args, **kwargs):
        self.enrichment_type = "provision_citation"
        super().save(*args, **kwargs)
