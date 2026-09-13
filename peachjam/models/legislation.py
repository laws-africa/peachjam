from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.decorators import LegislationDecorator
from peachjam.models import (
    CoreDocument,
    CoreDocumentManager,
    CoreDocumentQuerySet,
    Work,
)


class LegislationManager(CoreDocumentManager):
    def get_queryset(self):
        # defer expensive fields
        return super().get_queryset().defer("timeline_json", "commencements_json")


class Legislation(CoreDocument):
    decorator = LegislationDecorator()

    objects = LegislationManager.from_queryset(CoreDocumentQuerySet)()

    timeline_json = models.JSONField(
        _("timeline JSON"), null=False, blank=False, default=list
    )
    commencements_json = models.JSONField(
        _("commencements JSON"), null=False, blank=False, default=list
    )
    repealed = models.BooleanField(_("repealed"), default=False, null=False)
    parent_work = models.ForeignKey(
        Work, null=True, on_delete=models.PROTECT, verbose_name=_("parent work")
    )
    principal = models.BooleanField(_("principal"), default=False, null=False)

    frbr_uri_doctypes = ["act"]

    default_nature = ("act", "Act")

    class Meta(CoreDocument.Meta):
        verbose_name = _("legislation")
        verbose_name_plural = _("legislation")

    def __str__(self):
        return self.title

    def search_penalty(self):
        # non-principal (ie. amendment) works get a slight search penalty so that principal works
        # tend to appear above them in search results
        if self.metadata_json and self.metadata_json.get("principal", None) is False:
            return 10.0
        return super().search_penalty()

    @property
    def commenced(self):
        return self.metadata_json.get("commenced", None)

    @property
    def publication_page(self):
        return (self.metadata_json.get("publication_document") or {}).get("start_page")

    def pre_save(self):
        self.doc_type = "legislation"
        return super().pre_save()


class PopularLegislation(models.Model):
    work = models.OneToOneField(
        Work,
        limit_choices_to={
            "documents__doc_type": "legislation",
            "documents__locality__isnull": True,
            "documents__published": True,
        },
        on_delete=models.CASCADE,
        related_name="popular_legislation",
        verbose_name=_("legislation"),
    )
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        ordering = ("position", "pk")
        verbose_name = _("popular legislation")
        verbose_name_plural = _("popular legislation")

    def __str__(self):
        return self.work.title

    @classmethod
    def add_suggestions(cls, limit=10):
        """Fill empty positions with ranked national legislation."""
        from peachjam.models import PeachJamSettings

        existing_work_ids = list(cls.objects.values_list("work_id", flat=True))
        available_positions = max(0, limit - len(existing_work_ids))
        if not available_positions:
            return 0

        site_settings = PeachJamSettings.load()
        jurisdiction_id = site_settings.default_document_jurisdiction_id
        if jurisdiction_id is None:
            jurisdiction_ids = list(
                site_settings.document_jurisdictions.values_list("pk", flat=True)[:2]
            )
            if len(jurisdiction_ids) == 1:
                jurisdiction_id = jurisdiction_ids[0]
        if jurisdiction_id is None:
            return 0

        works = Work.objects.filter(
            documents__doc_type="legislation",
            documents__jurisdiction_id=jurisdiction_id,
            documents__locality__isnull=True,
            documents__published=True,
        ).exclude(pk__in=existing_work_ids)
        popular_ordering = ("-authority_score", "-pagerank", "title")
        constitution_id = (
            works.filter(title__icontains="constitution")
            .exclude(title__icontains="amendment")
            .order_by(*popular_ordering)
            .values_list("pk", flat=True)
            .first()
        )
        works = works.annotate(
            popular_priority=models.Case(
                models.When(pk=constitution_id, then=models.Value(0)),
                default=models.Value(1),
                output_field=models.IntegerField(),
            )
        ).order_by("popular_priority", *popular_ordering)
        work_ids = list(
            works.values_list("pk", flat=True).distinct()[:available_positions]
        )
        next_position = (
            cls.objects.aggregate(max_position=models.Max("position"))["max_position"]
            or 0
        ) + 1
        cls.objects.bulk_create(
            [
                cls(work_id=work_id, position=next_position + offset)
                for offset, work_id in enumerate(work_ids)
            ]
        )
        return len(work_ids)
