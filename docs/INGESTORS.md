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
