from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class LawReport(models.Model):
    title = models.CharField(_("title"), max_length=2048, unique=True)
    slug = models.CharField(max_length=2048, unique=True)
    entity_profile = GenericRelation("peachjam.EntityProfile", verbose_name="profile")

    class Meta:
        ordering = ("title",)
        verbose_name = _("law report")
        verbose_name_plural = _("law reports")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("law_report_detail", args=[self.slug])


class LawReportVolume(models.Model):

    title = models.CharField(_("title"), max_length=2048)
    slug = models.CharField(max_length=2048)
    year = models.PositiveIntegerField(null=True, blank=True)
    law_report = models.ForeignKey(
        LawReport, on_delete=models.CASCADE, related_name="volumes"
    )

    class Meta:
        ordering = ("title",)
        verbose_name = _("law report volume")
        verbose_name_plural = _("law report volumes")
        unique_together = ["law_report", "slug"]

    def __str__(self):
        return f"{self.law_report.title} - {self.title}"

    def get_absolute_url(self):
        return reverse(
            "law_report_volume_detail", args=[self.law_report.slug, self.slug]
        )


class LawReportEntry(models.Model):
    judgment = models.ForeignKey(
        "peachjam.Judgment", related_name="law_report_entries", on_delete=models.CASCADE
    )
    law_report_volume = models.ForeignKey(
        LawReportVolume, related_name="law_report_entries", on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = _("law report entry")
        verbose_name_plural = _("law report entries")

    def __str__(self):
        return f"{self.law_report_volume} - {self.judgment}"
