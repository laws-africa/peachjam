from django.db import models

from peachjam.models.core_document_model import CoreDocument


class CitationLink(models.Model):
    document = models.ForeignKey(
        CoreDocument, related_name="citation_links", on_delete=models.CASCADE
    )
    text = models.TextField(null=False, blank=False)
    url = models.URLField(max_length=1024)
    target_id = models.CharField(max_length=1024, null=False, blank=False)
    target_selectors = models.JSONField()

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
