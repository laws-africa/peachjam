from django.urls import include, path

from peachjam.views.generic_views import PageLoadedView, SentrySamplingView
from peachjam_search.views.history import SearchHistoryView

urlpatterns = [
    path("saved-documents/", include("peachjam.urls.saved_documents")),
    path("follow/", include("peachjam.urls.following")),
    path("loaded", PageLoadedView.as_view(), name="loaded"),
    path("search-history", SearchHistoryView.as_view(), name="search_history"),
    path(
        "sentry-sampling/<str:mode>/",
        SentrySamplingView.as_view(),
        name="sentry_sampling",
    ),
]
