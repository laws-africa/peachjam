from django.db import models
from django.utils.translation import gettext_lazy as _


class ProvisionLevelEnrichmentManager(models.Manager):
    # use e.g. doc.work.enrichments.unconstitutional_provisions()
    def unconstitutional_provisions(self):
        return self.filter(enrichment_type="unconstitutional_provision")


class ProvisionLevelEnrichment(models.Model):
    # TODO: add more choices
    ENRICHMENT_TYPE_CHOICES = (
        ("provision_enrichment", _("Provision enrichment")),
        ("unconstitutional_provision", _("Unconstitutional provision")),
    )

    source_id = models.IntegerField(_("source id"), null=False, blank=False)
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
    # whole_work = models.BooleanField(_("whole work"), default=False)
    enrichment_type = models.CharField(
        _("enrichment type"),
        max_length=256,
        choices=ENRICHMENT_TYPE_CHOICES,
        default="provision_enrichment",
        null=False,
        blank=False,
    )
    text = models.CharField(_("text"), max_length=2048, null=True, blank=True)

    objects = ProvisionLevelEnrichmentManager()

    class Meta:
        verbose_name = _("provision-level enrichment")
        verbose_name_plural = _("provision-level enrichments")

    @property
    def whole_work(self):
        return not self.provision_eid

    def save(self, *args, **kwargs):
        # if not self.provision:
        #     self.whole_work = True
        super().save(*args, **kwargs)


class UnconstitutionalProvision(ProvisionLevelEnrichment):
    # TODO: SET_NULL rather?
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
    # TODO: SET_NULL rather?
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
