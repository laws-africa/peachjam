from django.urls import include, path

from liiweb import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("gazettes", views.GazetteListView.as_view(), name="gazettes"),
    path("gazettes/<int:year>", views.YearView.as_view(), name="gazettes_by_year"),
    path("", include("peachjam.urls")),
]
