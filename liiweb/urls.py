from django.urls import include, path

urlpatterns = [
    path("", include("peachjam.urls")),
]
