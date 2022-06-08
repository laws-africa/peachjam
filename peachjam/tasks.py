from background_task import background

from peachjam.adapters import IndigoAdapter, IndigoUpdater

ADAPTERS = {"indigo_adapter": IndigoAdapter}


@background(remove_existing_tasks=True)
def init_adapter(adapter_name, url, token, last_refreshed):
    adapter = ADAPTERS[adapter_name](url, token, last_refreshed)
    updated_docs_list = adapter.get_updated_documents(last_refreshed)
    for updated_doc in updated_docs_list[:10]:
        update_document(token, updated_doc)


@background
def update_document(token, document):
    updater = IndigoUpdater(token)
    updater.update_document(document)


def setup_ingestors():
    from datetime import datetime

    from peachjam.models import Ingestor

    for ingestor in Ingestor.objects.all():
        init_adapter(
            ingestor.adapter,
            ingestor.url,
            ingestor.token,
            ingestor.last_refreshed_at.strftime("%m/%d/%Y, %H:%M:%S"),
            # repeat=5,
        )
        ingestor.last_refreshed_at = datetime.now()
        ingestor.save()
