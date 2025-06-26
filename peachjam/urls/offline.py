from django.urls import path

from peachjam.views.offline import OfflineView, service_worker

urlpatterns = [
    # MUST be at root to ensure it can cache all content
    path("offline-service-worker.js", service_worker),
    path("offline/offline", OfflineView.as_view()),
]
