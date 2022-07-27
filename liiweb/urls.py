from django.urls import include, path

from liiweb import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("", include("peachjam.urls")),
]
