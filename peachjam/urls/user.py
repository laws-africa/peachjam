from django.urls import include, path

from peachjam.views.generic_views import PageLoadedView, SentrySamplingView

urlpatterns = [
    path("saved-documents/", include("peachjam.urls.saved_documents")),
    path("follow/", include("peachjam.urls.following")),
    path("loaded", PageLoadedView.as_view(), name="loaded"),
    path(
        "sentry-sampling/<str:mode>/",
        SentrySamplingView.as_view(),
        name="sentry_sampling",
    ),
]
