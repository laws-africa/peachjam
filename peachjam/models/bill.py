from django.db import models
from django.utils.translation import gettext_lazy as _

from peachjam.decorators import BillDecorator
from peachjam.models import CoreDocument


class Bill(CoreDocument):

    decorator = BillDecorator()

    frbr_uri_doctypes = ["bill"]
    default_nature = ("bill", "Bill")
    author = models.ForeignKey(
        "peachjam.Author", null=True, on_delete=models.CASCADE, verbose_name=_("author")
    )

    author_label = _("Chamber")
    author_label_plural = _("Chambers")

    class Meta(CoreDocument.Meta):
        verbose_name = _("bill")
        verbose_name_plural = _("bills")

    def author_list(self):
        return [self.author] if self.author else []

    def prepare_and_set_expression_frbr_uri(self):
        self.frbr_uri_actor = self.author.code if self.author else None
        super().prepare_and_set_expression_frbr_uri()

    def pre_save(self):
        self.doc_type = "bill"
        return super().pre_save()
