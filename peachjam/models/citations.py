import logging
from datetime import timedelta
from random import randint

from django.db import models
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .settings import SingletonModel

log = logging.getLogger(__name__)


class CitationLink(models.Model):
    document = models.ForeignKey(
        "peachjam.CoreDocument",
        related_name="citation_links",
        on_delete=models.CASCADE,
        verbose_name=_("document"),
    )
    text = models.TextField(_("text"), null=False, blank=False)
    url = models.CharField(_("url"), max_length=1024)
    target_id = models.CharField(
        _("target id"), max_length=1024, null=False, blank=False
    )
    target_selectors = models.JSONField(verbose_name=_("target selectors"))

    class Meta:
        verbose_name = _("citation link")
        verbose_name_plural = _("citation links")

    def to_citator_api(self):
        """Transform into a format suitable for the Citator API."""
        selector = next(
            (t for t in self.target_selectors if t["type"] == "TextPositionSelector"),
            None,
        )
        return {
            "href": self.url,
            "text": self.text,
            # strip the page- and just keep the num
            "target_id": int(self.target_id.split("-", 1)[1]) - 1,
            "start": selector["start"] if selector else -1,
            "end": selector["end"] if selector else -1,
        }

    def __str__(self):
        return f"Citation link for {self.document.doc_type} - {self.document.title}"

    @classmethod
    def from_extracted_citation(cls, citation):
        """Create a new CitationLink object from an ExtractedCitation object."""
        # TODO: this currently assumes a plain-text citation
        return cls(
            text=citation.text,
            url=citation.href,
            target_id=f"page-{citation.target_id + 1}",
            target_selectors=[
                {
                    "type": "TextPositionSelector",
                    "start": citation.start,
                    "end": citation.end,
                },
                {
                    "type": "TextQuoteSelector",
                    "exact": citation.text,
                    "prefix": citation.prefix,
                    "suffix": citation.suffix,
                },
            ],
        )


class ExtractedCitation(models.Model):
    citing_work = models.ForeignKey(
        "peachjam.Work",
        null=False,
        on_delete=models.CASCADE,
        related_name="outgoing_citations",
        verbose_name=_("citing work"),
    )
    target_work = models.ForeignKey(
        "peachjam.Work",
        null=False,
        on_delete=models.CASCADE,
        related_name="incoming_citations",
        verbose_name=_("target work"),
    )
    treatments = models.ManyToManyField("Treatment", verbose_name=_("treatment"))

    @classmethod
    def for_citing_works(cls, work):
        # only returns works with an associated document
        return (
            cls.objects.prefetch_related("citing_work", "target_work")
            .filter(citing_work=work, target_work__documents__isnull=False)
            .order_by("target_work_id")
            .distinct("target_work")
        )

    @classmethod
    def for_target_works(cls, work):
        return (
            cls.objects.prefetch_related("citing_work", "target_work")
            .filter(target_work=work, citing_work__documents__isnull=False)
            .order_by("citing_work_id")
            .distinct("citing_work")
        )

    @classmethod
    def update_counts_for_work(cls, work):
        work.n_cited_works = cls.for_citing_works(work).count()
        work.n_citing_works = cls.for_target_works(work).count()
        work.save(update_fields=["n_cited_works", "n_citing_works"])

    @classmethod
    def fetch_grouped_citation_docs(
        self, works, language, n_per_group=10, offset=0, nature=None
    ):
        """Fetch documents for the given works, grouped by nature and ordered by the most incoming citations.
        Returns a list of documents ordered by nature, -citing works, title."""
        from .core_document import CoreDocument

        # get the best documents for these works
        docs = (
            CoreDocument.objects.filter(work__in=works)
            .distinct("work_frbr_uri")
            # we're fetching documents, so we want the most recent one for each work
            .order_by("work_frbr_uri", "-date")
            .preferred_language(language)
        )

        qs = (
            CoreDocument.objects.prefetch_related("work")
            .select_related("nature")
            .filter(pk__in=docs)
        )

        truncated = False
        # get the top n_per_group documents for each nature, ordering by the number of incoming citations
        if nature:
            # just one group, don't need a window function
            qs = qs.filter(nature=nature).order_by("-work__authority_score", "title")
            truncated = qs.count() > offset + n_per_group
            qs = qs[offset : offset + n_per_group]
        else:
            # use a window function to apply a row number within each nature group, ordering by number of citations
            # offset is not supported
            assert offset == 0
            qs = qs.annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F("nature__name")],
                    order_by=[F("work__authority_score").desc(), F("title")],
                )
            ).filter(row_number__lte=n_per_group)
        return (
            sorted(qs, key=lambda d: [d.nature.name, -d.work.authority_score, d.title]),
            truncated,
        )


class Treatment(models.Model):
    name = models.CharField(_("name"), max_length=4096, unique=True)

    def __str__(self):
        return self.name


class CitationProcessing(SingletonModel):
    processing_date = models.DateField(_("processing date"), null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = _("citation processing")

    def __str__(self):
        return "Citation processing"

    def queue_re_extract_citations(self, date):
        from peachjam.models import pj_settings
        from peachjam.tasks import re_extract_citations

        if pj_settings().re_extract_citations:
            if self.processing_date is None or date < self.processing_date:
                log.info("Updating processing date to %s", date)
                self.processing_date = date
                self.save()

                # run next saturday at a random hour, since it queues up a lot of other tasks
                now = timezone.now()
                at = now + timedelta(days=(5 - now.weekday()) % 7)
                at = at.replace(hour=randint(0, 23), minute=0, second=0, microsecond=0)
                re_extract_citations(schedule=at)

    def re_extract_citations(self):
        """
        Queues up background tasks to re-extract citations for all documents dated on or after the processing date.
        This is to handle the case where an older document has just been added to the system, and newer documents may
        therefore cite it.
        """
        from peachjam.models import CoreDocument
        from peachjam.tasks import extract_citations

        if self.processing_date:
            later_documents = (
                CoreDocument.objects.filter(date__gte=self.processing_date)
                .only("pk")
                .order_by("date")
            )
            log.info(
                "Re-extracting citations for %s documents since date %s",
                later_documents.count(),
                self.processing_date,
            )

            for pk in later_documents.values_list("pk", flat=True):
                extract_citations(pk, creator=CoreDocument(pk=pk))

            self.reset_processing_date()

    def reset_processing_date(self):
        """Reset the processing date to None."""
        log.info("Resetting processing date.")
        self.processing_date = None
        self.save()


def citations_processor():
    """Return the CitationProcessing object."""
    return CitationProcessing.load()
