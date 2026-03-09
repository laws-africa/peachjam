from django.utils.translation import gettext_lazy as _

from peachjam.admin import DocumentAdmin
from peachjam_ml.models import DocumentEmbedding
from peachjam_ml.tasks import update_document_embeddings


def update_chunk_embeddings(self, request, queryset):
    for document in queryset:
        update_document_embeddings(document.id)

    self.message_user(
        request,
        _("Updating document chunks and embeddings in the background."),
    )


update_chunk_embeddings.short_description = _(
    "Update document chunks and embeddings (background)"
)


def update_doc_embeddings(self, request, queryset):
    for doc_embedding in (
        DocumentEmbedding.objects.filter(document__in=queryset)
        .defer("text_embedding")
        .iterator(100)
    ):
        doc_embedding.update_embedding()
        doc_embedding.save()

    self.message_user(
        request,
        _("Re-calculated document embeddings."),
    )


update_doc_embeddings.short_description = _("Re-calculate average document embeddings")


DocumentAdmin.actions.append("update_chunk_embeddings")
DocumentAdmin.actions.append("update_doc_embeddings")
DocumentAdmin.update_doc_embeddings = update_doc_embeddings
DocumentAdmin.update_chunk_embeddings = update_chunk_embeddings
