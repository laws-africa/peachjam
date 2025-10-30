from django.urls import include, path, re_path

from liiweb import views

# these urls do NOT get i18n language prefixes
urlpatterns = [
    # This redirects old Ulii case laws to work with peachjam urls
    re_path(
        r"^(?P<country>[a-z]{2})/judgment/(?P<court>[-\w]+)/(?P<year>\d+)/(?P<number>\d+)$",
        views.RedirectCaseURLsView.as_view(),
        name="old_lii_case_redirect",
    ),
    path("", include("peachjam.urls.non_i18n")),
]
