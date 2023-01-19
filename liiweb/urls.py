from django.urls import include, path

from liiweb import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
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
    path(
        "legislation/regulations",
        views.LegislationListView.as_view(variant="subleg"),
        name="legislation_list_regulations",
    ),
    path("", include("peachjam.urls")),
]
