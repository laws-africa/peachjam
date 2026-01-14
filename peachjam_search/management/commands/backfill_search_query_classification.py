from django.core.management.base import BaseCommand

from peachjam_search.classifier import QueryClassifier
from peachjam_search.models import SearchTrace


class Command(BaseCommand):
    help = (
        "Backfill the query classification fields for existing SearchTrace records "
        "that are missing them."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of SearchTrace objects to process (default: 1000).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit is not None and limit <= 0:
            self.stdout.write("Limit is zero or negative, nothing to do.")
            return

        qs = (
            SearchTrace.objects.filter(query_clean__isnull=True)
            .order_by("-created_at")
            .only("pk", "search")
        )
        if limit is not None:
            qs = qs[:limit]

        classifier = QueryClassifier()
        processed = 0

        for trace in qs:
            qclass = classifier.classify(trace.search or "")
            SearchTrace.objects.filter(pk=trace.pk).update(
                query_clean=qclass.query_clean,
                query_clean_n_words=qclass.n_words,
                query_clean_n_chars=qclass.n_chars,
                query_classification=(qclass.label.value if qclass.label else None),
                query_classification_confidence=qclass.confidence,
            )
            processed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Backfilled {processed} search trace(s).")
        )
