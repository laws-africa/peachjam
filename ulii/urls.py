from django.urls import include, path, re_path

from liiweb.views import RedirectCaseURLsView
from ulii import views

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home_page"),
    # This redirects old Ulii case laws to work with peachjam urls
    re_path(
        r"^ug/judgment/(?P<court>[-\w]+)/(?P<year>\d+)/(?P<number>\d+)$",
        RedirectCaseURLsView.as_view(),
        name="old_lii_case_redirect",
    ),
    path("", include("liiweb.urls")),
]
