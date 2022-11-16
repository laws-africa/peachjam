from django.conf.urls import url
from django.urls import include, path

from lawlibrary import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    path("judgments/", views.JudgmentListView.as_view(), name="judgment_list"),
    path("legislation/", views.LegislationListView.as_view(), name="legislation_list"),
    path(
        "legislation/provincial",
        views.ProvincialLegislationView.as_view(),
        name="provincial_legislation",
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
        "legislation/<str:code>/",
        views.ProvincialLegislationListView.as_view(),
        name="provincial_legislation_list",
    ),
    path(
        "legislation/<str:code>/repealed",
        views.ProvincialLegislationListView.as_view(variant="repealed"),
        name="provincial_legislation_list_repealed",
    ),
    path(
        "legislation/<str:code>/all",
        views.ProvincialLegislationListView.as_view(variant="all"),
        name="provincial_legislation_list_all",
    ),
    path("gazettes", views.LawLibraryGazetteListView.as_view(), name="gazettes"),
    path(
        "gazettes/<int:year>",
        views.LawLibraryYearView.as_view(),
        name="gazettes_by_year",
    ),
    path(
        "gazettes/<str:code>/",
        views.ProvincialGazetteListView.as_view(),
        name="provincial_gazette_list",
    ),
    url(
        r"^gazettes/(?P<code>\w+)/(?P<year>\w+)/$",
        views.LawLibraryYearView.as_view(),
        name="gazettes_by_year",
    ),
    path("", include("liiweb.urls")),
]
