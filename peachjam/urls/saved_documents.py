from django.urls import path

from peachjam.views import (
    SavedDocumentCreateView,
    SavedDocumentDeleteView,
    SavedDocumentFragmentsView,
    SavedDocumentModalView,
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
        "<int:pk>/modal",
        SavedDocumentModalView.as_view(),
        name="saved_document_modal",
    ),
]
