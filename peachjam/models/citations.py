import logging

from django.db import models
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
                re_extract_citations()

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
            for document in later_documents.iterator():
                extract_citations(document.id)

            self.reset_processing_date()

    def reset_processing_date(self):
        """Reset the processing date to None."""
        log.info("Resetting processing date.")
        self.processing_date = None
        self.save()


def citations_processor():
    """Return the CitationProcessing object."""
    return CitationProcessing.load()
