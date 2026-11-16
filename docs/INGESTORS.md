# Ingestors

Ingestors are scheduled import adapters for external content sources. The
database model is `peachjam.models.Ingestor`; the adapter implementation is
selected from the `ingestor-adapter` plugin registry using the model's
`adapter` field.

## Refresh lifecycle

Scheduled work starts in `peachjam.tasks.run_ingestor()`, which calls
`Ingestor.check_for_updates()`.

`Ingestor.check_for_updates()`:

- builds the configured adapter with its `IngestorSetting` values
- passes `last_refreshed_at` to `adapter.check_for_updates(last_refreshed_at)`
- expects an `(updated, deleted)` tuple
- queues `peachjam.tasks.update_document(ingestor_id, document_id)` for each
  updated identifier
- queues `peachjam.tasks.delete_document(ingestor_id, document_id)` for each
  deleted identifier
- stores the refresh start time as `last_refreshed_at`

The values returned in `updated` and `deleted` are adapter-specific opaque
identifiers. They are often expression FRBR URIs or source API URLs, but they
can also be sentinels for adapter-wide work.

## Update lifecycle

`peachjam.tasks.update_document()` calls `Ingestor.update_document()`, which
recreates the adapter and passes the opaque identifier to
`adapter.update_document(document_id)`.

Adapters must therefore keep `check_for_updates()` and `update_document()` in
sync: every identifier returned by `check_for_updates()` must be understood by
`update_document()`.

## Indigo adapters

`IndigoAdapter` uses Indigo API document URLs as update identifiers. Its
`check_for_updates()` gets work-expression lists from Indigo, compares remote
`updated_at` values to `last_refreshed_at`, and returns expression URLs. Its
`update_document(url)` fetches `f"{url}.json"` and imports or updates the local
`CoreDocument`.

`IndigoEnrichmentDatasetIngestor` is a specialization for provision-topic
enrichment datasets. It has two update identifier types:

- `dataset`: a sentinel that means re-import the whole enrichment dataset
- Indigo document URLs: delegated to `IndigoAdapter.update_document()`

During refresh, it fetches the enrichment dataset and extracts work FRBR URIs
from each enrichment's `work` field. It fetches each referenced Indigo work and
queues all expression URLs when the local system has no document for that work,
or when the remote work/expression changed since the last refresh.

Dataset imports and document imports are queued as separate background tasks.
If a document is fetched because an enrichment references a missing work, the
dataset import may not see that document until a later scheduled refresh unless
the dataset itself was also queued and happens to run after the document import.

## Gazettes from another Peachjam site

`PeachjamGazetteAdapter` imports gazettes and PDFs from another Peachjam site's
API. `GazetteAPIAdapter` continues to serve the legacy Gazettes.Africa archive
API and its shared S3 files.

For Kenya Law, create an ingestor on Gazettes.Africa with adapter
`PeachjamGazetteAdapter` and these settings:

| Setting | Value |
| --- | --- |
| `api_url` | `https://example.com/api/v1` |
| `token` | A token for a Kenya Law account with `peachjam.api_gazette` permission |
| `jurisdiction` | `KE` (optional filter) |

Deploy the shared gazette API changes before enabling the ingestor.
An initial refresh without `last_refreshed_at` records a cutoff without fetching
historical gazettes. Later refreshes use `updated_at__gte`. Existing identifiers
are reused, and identical PDFs are not replaced.

### Initial Kenya reconciliation

Many Kenya Law gazettes originally came from Gazettes.Africa and still refer to
its PDFs. Compare exports externally instead of running a full archive import.

1. Create the import ingestor disabled. On Gazettes.Africa, record the cutoff
   **before exporting either collection**, so incremental refreshes cover changes
   made while the exports and comparison are in progress:

   ```python
   from django.utils import timezone
   from peachjam.models import Ingestor

   ingestor = Ingestor.objects.get(pk=IMPORT_INGESTOR_ID)
   ingestor.last_refreshed_at = timezone.now()
   ingestor.save(update_fields=["last_refreshed_at"])
   ```

2. In `manage.py shell` on each site, export the Kenyan gazette identifiers and
   timestamps. Save the files as `kenyalaw.csv` and `gazettes.csv` respectively:

   ```python
   import csv
   from peachjam.models import Gazette

   with open("/tmp/kenya-gazettes.csv", "w", newline="") as output:
       writer = csv.writer(output)
       writer.writerow(["expression_frbr_uri", "updated_at"])
       for uri, updated in Gazette.objects.filter(jurisdiction_id="KE").order_by("pk").values_list(
           "expression_frbr_uri", "updated_at"
       ).iterator():
           writer.writerow([uri, updated.isoformat()])
   ```

3. Copy the exports to a local directory and compare them:

   ```sh
   python scripts/compare-kenya-gazettes.py kenyalaw.csv gazettes.csv > candidates.csv
   ```

   The script selects missing gazettes and all differing timestamps,
   excluding other jurisdictions and document types. Review the candidates before
   queuing: `updated_at` reflects local saves, so timestamp differences alone do
   not prove that the underlying gazette or PDF changed. Save the selected rows
   as `reviewed.csv`; neither export nor comparison changes either site.

4. Enable the import ingestor, retaining the recorded cutoff. In a Gazettes.Africa
   shell, queue only the reviewed identifiers using the existing background task:

   ```python
   import csv
   from peachjam.tasks import update_document

   with open("reviewed.csv", newline="") as selected:
       for row in csv.DictReader(selected):
           update_document(IMPORT_INGESTOR_ID, row["expression_frbr_uri"])
   ```

   Scheduled refreshes continue incrementally from the cutoff. A missing source
   document is skipped; a failed PDF download leaves the local record unchanged.

### Kenya deletion checks

Create a separate ingestor with adapter `PeachjamGazetteDeleteAdapter`, the same
Kenya Law `api_url` and `token`, and optional `batch_range` (default 10000).
Its scope is fixed to Kenyan gazettes, including historical records created by
other ingestors; a `jurisdiction` setting cannot widen it.

Like `JudgmentDeleteAdapter`, it uses `get_deleted_documents` to send batches to
`/api/v1/validate-gazette-expression-frbr-uris` and queues `delete_document` for
missing identifiers. Batches use fixed primary-key ranges so earlier deletions
cannot shift later batches. The deletion task re-checks the source detail endpoint
and deletes only on HTTP 404. Authentication, network and server errors do not cause deletion.
Deleting a local gazette record does not delete the potentially shared PDF object.
Enable this ingestor after reviewing the initial reconciliation.
