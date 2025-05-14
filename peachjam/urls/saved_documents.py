from django.urls import path

from peachjam.views import (
    SavedDocumentButtonBulkView,
    SavedDocumentButtonView,
    SavedDocumentCreateView,
    SavedDocumentDeleteView,
    SavedDocumentTableBulkView,
    SavedDocumentUpdateView,
)

urlpatterns = [
    path(
        "button/<int:doc_id>",
        SavedDocumentButtonView.as_view(),
        name="saved_document_button",
    ),
    path(
        "buttons/",
        SavedDocumentButtonBulkView.as_view(),
    ),
    path(
        "table/",
        SavedDocumentTableBulkView.as_view(),
    ),
    path(
        "create",
        SavedDocumentCreateView.as_view(),
        name="saved_document_create",
    ),
    path(
        "<int:pk>/update",
        SavedDocumentUpdateView.as_view(),
        name="saved_document_update",
    ),
    path(
        "<int:pk>/delete",
        SavedDocumentDeleteView.as_view(),
        name="saved_document_delete",
    ),
]
