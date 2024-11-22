from django.urls import include, path

from open_by_laws.views import HomePageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home_page"),
    path("", include("liiweb.urls")),
]
