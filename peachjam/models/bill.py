from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.models import CoreDocument


class Bill(CoreDocument):
    frbr_uri_doctypes = ["bill"]
    default_nature = ("bill", "Bill")
    author = models.ForeignKey(
        "peachjam.Author", null=True, on_delete=models.CASCADE, verbose_name=_("author")
    )

    class Meta(CoreDocument.Meta):
        verbose_name = _("bill")
        verbose_name_plural = _("bills")

    def prepare_and_set_expression_frbr_uri(self):
        self.frbr_uri_actor = self.author.code if self.author else None
        super().prepare_and_set_expression_frbr_uri()

    def pre_save(self):
        self.doc_type = "bill"
        return super().pre_save()
