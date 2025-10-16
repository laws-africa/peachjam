from django.urls import path, re_path

from .views import (
    DocumentChatView,
    SimilarDocumentsDocumentDetailView,
    SimilarDocumentsFolderView,
    StartDocumentChatView,
)

urlpatterns = [
    re_path(
        r"^(?P<frbr_uri>akn/.*)/similar-documents$",
        SimilarDocumentsDocumentDetailView.as_view(),
        name="document_similar_docs",
    ),
    path(
        "user/folder/<int:pk>/similar-documents",
        SimilarDocumentsFolderView.as_view(),
        name="folder_similar_docs",
    ),
    path("api/documents/<int:pk>/chat", StartDocumentChatView.as_view()),
    path("api/chats/<str:pk>", DocumentChatView.as_view()),
]
