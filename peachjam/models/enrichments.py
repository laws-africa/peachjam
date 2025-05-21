from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from lxml import etree
from polymorphic.models import PolymorphicManager, PolymorphicModel


class ProvisionEnrichmentManager(PolymorphicManager):
    # use e.g. doc.work.enrichments.unconstitutional_provisions()
    def unconstitutional_provisions(self):
        return self.filter(enrichment_type="unconstitutional_provision")


class ProvisionEnrichment(PolymorphicModel):
    # TODO: add more choices
    ENRICHMENT_TYPE_CHOICES = (
        ("provision_enrichment", _("Provision enrichment")),
        ("unconstitutional_provision", _("Unconstitutional provision")),
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

    objects = ProvisionEnrichmentManager()

    class Meta:
        verbose_name = _("provision enrichment")
        verbose_name_plural = _("provision enrichments")

    def __str__(self):
        return f"{self.enrichment_type} - {self.work} - {self.provision_eid or 'whole work'}"

    @cached_property
    def provision_by_eid(self):
        html_content = self.work.documents.latest_expression().first().content_html
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
        # TODO: better place to get this document
        document = self.work.documents.latest_expression().first()
        if document and document.toc_json:

            def find_toc_item(toc, eid):
                for item in toc:
                    if item["id"] == eid:
                        return item

                    if item["id"] and eid.startswith(f"{item['id']}__"):
                        if item["children"]:
                            # descend into children
                            found = find_toc_item(item["children"], eid)
                            if found:
                                return found

                        # closest match
                        return item

            item = find_toc_item(document.toc_json, self.provision_eid)
            # TODO: get remaining portion if we couldn't go far enough down
            # which is all the akn-num text between item and the provision
            return item["title"] if item else self.provision_eid

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
