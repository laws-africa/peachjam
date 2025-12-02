from django.urls import path, re_path

from .views import (
    DocumentChatView,
    SimilarDocumentsDocumentDetailView,
    SimilarDocumentsFolderView,
    StartDocumentChatView,
    VoteChatMessageView,
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
    path("api/chats/<str:pk>/stream", DocumentChatView.as_view()),
    path(
        "api/chats/<str:pk>/messages/<str:message_id>/vote-up",
        VoteChatMessageView.as_view(up=True),
    ),
    path(
        "api/chats/<str:pk>/messages/<str:message_id>/vote-down",
        VoteChatMessageView.as_view(up=False),
    ),
]
