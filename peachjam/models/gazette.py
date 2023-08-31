from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument


class Gazette(CoreDocument):
    class Meta(CoreDocument.Meta):
        verbose_name = _("gazette")
        verbose_name_plural = _("gazettes")
        permissions = [("api_gazette", "API gazette access")]

    def pre_save(self):
        self.frbr_uri_doctype = "officialGazette"
        self.doc_type = "gazette"
        super().pre_save()
