from django.urls import include, path

from seylii.views import DonatePageView

urlpatterns = [
    path("donate/", DonatePageView.as_view(), name="donate"),
    path("", include("liiweb.urls")),
]
