from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legislation/provincial",
        views.LocalityLegislationView.as_view(variant="provincial"),
        name="locality_legislation",
    ),
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
        "legislation/uncommenced",
        views.LegislationListView.as_view(variant="uncommenced"),
        name="legislation_list_uncommenced",
    ),
    path(
        "legislation/subsidiary",
        views.LegislationListView.as_view(variant="subleg"),
        name="legislation_list_subsidiary",
    ),
    path(
        "legislation/recent",
        views.LegislationListView.as_view(variant="recent"),
        name="legislation_list_recent",
    ),
    path(
        "legislation/<str:code>/",
        views.LocalityLegislationListView.as_view(),
        name="locality_legislation_list",
    ),
    path(
        "legislation/<str:code>/repealed",
        views.LocalityLegislationListView.as_view(variant="repealed"),
        name="locality_legislation_list_repealed",
    ),
    path(
        "legislation/<str:code>/subsidiary",
        views.LocalityLegislationListView.as_view(variant="subleg"),
        name="locality_legislation_list_subsidiary",
    ),
    path(
        "legislation/<str:code>/all",
        views.LocalityLegislationListView.as_view(variant="all"),
        name="locality_legislation_list_all",
    ),
    path(
        "legislation/municipal",
        views.LocalityLegislationView.as_view(variant="municipal"),
        name="municipal_legislation",
    ),
    path("", include("liiweb.urls")),
]
