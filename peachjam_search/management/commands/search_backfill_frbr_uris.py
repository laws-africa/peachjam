from django.core.management.base import BaseCommand
from django_elasticsearch_dsl.registries import registry
from elasticsearch import helpers
from elasticsearch_dsl.connections import connections

from peachjam.models import CoreDocument


class Command(BaseCommand):
    def handle(self, *args, **options):
        # bulk get required document details to make this faster
        self.stdout.write("Preloading document details...")
        self.docs_by_id = {
            d.id: d
            for d in CoreDocument.objects.only("id", "work")
            .select_related("work")
            .iterator(chunk_size=1000)
        }
        self.stdout.write(f"Loaded {len(self.docs_by_id)} documents")

        self.client = connections.get_connection()

        for ix in registry.get_indices():
            if ix._mapping:
                self.backfill_index(ix)

    def backfill_index(self, ix):
        self.stdout.write(f"Adding frbr_uri fields for {ix._name}")
        bulk_size = 10  # Process 10 documents at a time

        # Query to find documents where frbr_uri_country does not exist
        query = {
            "_source": [],
            "query": {"bool": {"must_not": {"exists": {"field": "frbr_uri_country"}}}},
        }

        bulk_updates = []
        count = 0

        for doc in helpers.scan(self.client, index=ix._name, query=query, size=50):
            doc_id = doc["_id"]
            if doc_id not in self.docs_by_id:
                continue
            work = self.docs_by_id[doc_id].work

            update_action = {
                "_op_type": "update",
                "_index": ix._name,
                "_id": doc_id,
                "doc": {
                    "frbr_uri_country": work.frbr_uri_country,
                    "frbr_uri_locality": work.frbr_uri_locality or "",
                    "frbr_uri_place": work.frbr_uri_place,
                    "frbr_uri_doctype": work.frbr_uri_doctype,
                    "frbr_uri_subtype": work.frbr_uri_subtype or "",
                    "frbr_uri_actor": work.frbr_uri_actor or "",
                },
            }
            bulk_updates.append(update_action)
            if len(bulk_updates) >= bulk_size:
                count += len(bulk_updates)
                self.stdout.write(f"Updated {count}")
                helpers.bulk(self.client, bulk_updates)
                bulk_updates.clear()

        if bulk_updates:
            helpers.bulk(self.client, bulk_updates)

        self.stdout.write("Done")
