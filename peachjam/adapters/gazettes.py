import logging

from peachjam.plugins import plugins

from .adapters import Adapter

log = logging.getLogger(__name__)


@plugins.register("gazette-adapter")
class GazetteAdapter(Adapter):
    def check_for_updates(self, last_refreshed):
        log.info("Checking for new gazettes...")
        return

    def update_document(self, document_id):
        log.info("Updating new gazettes...")
        return
