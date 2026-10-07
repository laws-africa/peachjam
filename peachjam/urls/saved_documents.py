from django.urls import path

from peachjam.views import (
    SavedDocumentCreateView,
    SavedDocumentDeleteView,
    SavedDocumentFragmentsView,
    SavedDocumentModalView,
    SavedDocumentRemoveFromFolderView,
    SavedDocumentUpdateView,
)

urlpatterns = [
    path(
        "fragments",
        SavedDocumentFragmentsView.as_view(),
        name="saved_document_fragments",
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
    path(
        "<int:pk>/folders/<int:folder_pk>/remove",
        SavedDocumentRemoveFromFolderView.as_view(),
        name="saved_document_remove_from_folder",
    ),
    path(
        "<int:pk>/modal",
        SavedDocumentModalView.as_view(),
        name="saved_document_modal",
    ),
]
