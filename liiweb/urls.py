from django.urls import include, path

from liiweb import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("pocketlaw", views.PocketlawView.as_view(), name="pocketlaw"),
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legislation/repealed",
        views.LegislationListView.as_view(variant="repealed"),
        name="legislation_list_repealed",
    ),
    path(
        "legislation/all",
        views.LegislationListView.as_view(variant="all"),
        name="legislation_list_all",
    ),
    path("", include("peachjam.urls")),
]
