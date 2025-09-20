from django.urls import include, path

from peachjam.views.generic_views import MessagesView

urlpatterns = [
    path("saved-documents/", include("peachjam.urls.saved_documents")),
    path("follow/", include("peachjam.urls.following")),
    path("messages", MessagesView.as_view(), name="messages"),
]
