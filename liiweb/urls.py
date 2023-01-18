from django.urls import include, path, re_path

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
    # This redirects old Ulii case laws to work with peachjam urls
    re_path(
        r"^(?P<country>[a-z]{2})/judgment/(?P<court>[-\w]+)/(?P<year>\d+)/(?P<number>\d+)$",
        views.RedirectCaseURLsView.as_view(),
        name="old_lii_case_redirect",
    ),
    path("", include("peachjam.urls")),
]
