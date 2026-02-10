from django.urls import path

from peachjam.views.chat import (
    DocumentChatView,
    StartDocumentChatView,
    VoteChatMessageView,
)

urlpatterns = [
    path(
        "api/documents/<int:pk>/chat",
        StartDocumentChatView.as_view(),
        name="document_chat",
    ),
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
