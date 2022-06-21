from django.db import models

from peachjam.models import CoreDocument


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
