import logging

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from peachjam.plugins import plugins
from peachjam.tasks import delete_document, update_document

log = logging.getLogger(__name__)


class IngestorSetting(models.Model):
    name = models.CharField(_("name"), max_length=2048)
    value = models.CharField(_("value"), max_length=2048, blank=True, default="")
    ingestor = models.ForeignKey(
        "peachjam.Ingestor", on_delete=models.CASCADE, verbose_name=_("ingestor")
    )

    class Meta:
        verbose_name = _("ingestor setting")
        verbose_name_plural = _("ingestor settings")

    def __str__(self):
        return f"{self.name} = {self.value}"


class Ingestor(models.Model):
    adapter = models.CharField(_("adapter"), max_length=2048)
    last_refreshed_at = models.DateTimeField(
        _("last refreshed at"), null=True, blank=True
    )
    name = models.CharField(_("name"), max_length=255)
    enabled = models.BooleanField(_("enabled"), default=True)

    class Meta:
        verbose_name = _("ingestor")
        verbose_name_plural = _("ingestor")

    def __str__(self):
        return self.name

    def check_for_updates(self):
        adapter = self.get_adapter()
        log.info(
            f"Checking for ingestor updates for {self}, last_refresh_at {self.last_refreshed_at}"
        )
        updated, deleted = adapter.check_for_updates(self.last_refreshed_at)
        log.info(f"{len(updated)} documents to update")
        for doc in updated:
            update_document(self.id, doc)
        log.info(f"{len(deleted)} documents to delete")
        for doc in deleted:
            delete_document(self.id, doc)

        self.last_refreshed_at = timezone.now()
        self.save()
        log.info(f"Finished checking for ingestor updates for {self}")

    def update_document(self, document_id):
        adapter = self.get_adapter()
        adapter.update_document(document_id)

    def delete_document(self, expression_frbr_uri):
        adapter = self.get_adapter()
        adapter.delete_document(expression_frbr_uri)

    def handle_webhook(self, data):
        adapter = self.get_adapter()
        adapter.handle_webhook(data)

    def get_adapter(self):
        klass = plugins.registry["ingestor-adapter"][self.adapter]
        ingestor_settings = IngestorSetting.objects.filter(ingestor=self)
        settings = {s.name: s.value for s in ingestor_settings}
        return klass(self, settings)
