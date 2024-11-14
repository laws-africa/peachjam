from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument


class Bill(CoreDocument):
    frbr_uri_doctypes = ["bill"]
    default_nature = ("bill", "Bill")

    class Meta(CoreDocument.Meta):
        verbose_name = _("bill")
        verbose_name_plural = _("bills")

    def pre_save(self):
        self.doc_type = "bill"
        return super().pre_save()
