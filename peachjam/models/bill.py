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
        if not self.frbr_uri_actor:
            if self.author and self.author.code:
                raw_code = str(self.author.code).lower()

                prefix = "c_" if raw_code[0].isdigit() else ""
                max_length = 100
                max_code_length = max_length - len(prefix)

                self.frbr_uri_actor = f"{prefix}{raw_code[:max_code_length]}"
            else:
                self.frbr_uri_actor = None

        return super().prepare_and_set_expression_frbr_uri()

    def pre_save(self):
        self.doc_type = "bill"
        return super().pre_save()
