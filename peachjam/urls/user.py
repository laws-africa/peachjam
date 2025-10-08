from django.urls import include, path

from peachjam.views.generic_views import PageLoadedView

urlpatterns = [
    path("saved-documents/", include("peachjam.urls.saved_documents")),
    path("follow/", include("peachjam.urls.following")),
    path("loaded", PageLoadedView.as_view(), name="loaded"),
]
