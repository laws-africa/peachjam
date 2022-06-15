import logging

from background_task import background
from django.utils import timezone
from requests.exceptions import ConnectionError

from peachjam.adapters import IndigoAdapter, IndigoUpdater

logger = logging.getLogger(__name__)

ADAPTERS = {"indigo_adapter": IndigoAdapter}


def init_adapter(adapter_name, url, token, last_refreshed):
    adapter = ADAPTERS[adapter_name](url, token, last_refreshed)
    updated_docs_list = adapter.get_updated_documents(last_refreshed)
    for updated_doc in updated_docs_list:
        update_document(token, updated_doc)


@background
def update_document(token, document):
    updater = IndigoUpdater(token)
    updater.update_document(document)


@background(remove_existing_tasks=True)
def setup_ingestors():
    logger.info("starting ingestors...")
    from peachjam.models import Ingestor

    try:
        for ingestor in Ingestor.objects.all():
            last_refreshed = ingestor.last_refreshed_at
            ingestor.last_refreshed_at = timezone.now()
            ingestor.save()
            init_adapter(
                ingestor.adapter,
                ingestor.url,
                ingestor.token,
                last_refreshed.isoformat() if last_refreshed else None,
            )
    except ConnectionError as e:
        logger.error(e)
