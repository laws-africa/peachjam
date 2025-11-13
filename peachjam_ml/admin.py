import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from peachjam.admin import DocumentAdmin, UserAdminCustom
from peachjam_ml.models import ChatThread, DocumentEmbedding
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


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "document_link", "score", "updated_at")
    readonly_fields = (
        "id",
        "user",
        "document_link",
        "score",
        "created_at",
        "updated_at",
        "state_display",
    )
    fields = (
        "id",
        "user",
        "document_link",
        "score",
        "created_at",
        "updated_at",
        "state_display",
    )
    date_hierarchy = "updated_at"
    list_select_related = ("user", "document")
    search_fields = ("id", "user__username", "document__title")

    def has_add_permission(self, request):
        return False

    def document_link(self, obj):
        return format_html(
            "<a href='{}'>{}</a>", obj.document.get_absolute_url(), obj.document
        )

    document_link.short_description = _("Document")

    def state_display(self, obj):
        if not obj.state_json:
            return "-"
        formatted = json.dumps(obj.state_json, indent=2, sort_keys=True)
        return format_html("<pre>{}</pre>", formatted)

    state_display.short_description = _("State JSON")


class ChatThreadInline(admin.TabularInline):
    model = ChatThread
    extra = 0
    can_delete = False
    fields = ("updated_at", "document_link", "score")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def document_link(self, obj):
        return format_html(
            "<a href='{}'>{}</a>", obj.document.get_absolute_url(), obj.document
        )

    document_link.short_description = _("Document")


if ChatThreadInline not in UserAdminCustom.inlines:
    UserAdminCustom.inlines.append(ChatThreadInline)
