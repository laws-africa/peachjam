from django.urls import include, path

urlpatterns = [
    path("accounts/", include("peachjam.urls.accounts")),
    path("", include("peachjam_subs.urls")),
    path("", include("peachjam_ml.urls")),
]
