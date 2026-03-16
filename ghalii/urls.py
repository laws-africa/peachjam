from django.urls import include, path

urlpatterns = [
    path("", include("peachjam_ml.urls")),
    path("", include("liiweb.urls")),
]
