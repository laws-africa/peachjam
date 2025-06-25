from django.urls import path

from peachjam.views.offline import service_worker

urlpatterns = [path("offline-service-worker.js", service_worker)]
