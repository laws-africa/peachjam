from django.urls import include, path, re_path

from liiweb import views
from liiweb.views.donate import DonatePageView

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
    path(
        "legislation/subsidiary",
        views.LegislationListView.as_view(variant="subleg"),
        name="legislation_list_subsidiary",
    ),
    # This redirects old Ulii case laws to work with peachjam urls
    re_path(
        r"^(?P<country>[a-z]{2})/judgment/(?P<court>[-\w]+)/(?P<year>\d+)/(?P<number>\d+)$",
        views.RedirectCaseURLsView.as_view(),
        name="old_lii_case_redirect",
    ),
    path("donate/", DonatePageView.as_view(), name="donate"),
    path("", include("peachjam.urls")),
]
