from django.conf import settings
from django.core.management.base import BaseCommand

from peachjam.models import CoreDocument
from peachjam_ml.models import DocumentEmbedding


class Command(BaseCommand):
    help = "Backfill content chunks and embeddings from Elasticsearch for all documents"

    def handle(self, *args, **kwargs):
        qs = CoreDocument.objects.exclude(
            doc_type__in=settings.PEACHJAM["SEARCH_SEMANTIC_EXCLUDE_DOCTYPES"]
        )
        # exclude documents that are already have embeddings
        qs = qs.filter(embedding__isnull=True)
        qs = qs.order_by("-id")

        for document in qs.iterator(100):
            print(document.id)
            DocumentEmbedding.backfill_from_es(document)
