from django.utils.translation import gettext_lazy as _

from peachjam.admin import DocumentAdmin
from peachjam_ml.tasks import update_document_embeddings


def update_embeddings(self, request, queryset):
    for document in queryset:
        update_document_embeddings(document.id)

    self.message_user(
        request,
        _("Updating document embeddings in the background."),
    )


update_embeddings.short_description = _("Update document embeddings (background)")


DocumentAdmin.actions.append("update_embeddings")
DocumentAdmin.update_embeddings = update_embeddings
