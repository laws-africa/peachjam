from django.urls import path

from peachjam.views.offline import (
    OfflineHomeView,
    OfflineView,
    TaxonomyManifestView,
    service_worker,
)

urlpatterns = [
    # MUST be at root to ensure it can cache all content
    path("offline-service-worker.js", service_worker),
    path("offline/", OfflineHomeView.as_view(), name="offline"),
    path("offline/offline", OfflineView.as_view()),
    path("offline/taxonomy/<int:pk>/manifest.json", TaxonomyManifestView.as_view()),
]
