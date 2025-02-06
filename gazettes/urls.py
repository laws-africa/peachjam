from django.urls import include, path, re_path
from django.views.generic import RedirectView

from gazettes import views

urlpatterns = [
    # gazettes.africa
    path("", views.JurisdictionListView.as_view(), name="home"),
    path("archive/<path:path>", views.ArchiveView.as_view(), name="archive"),
    path("gazettes", RedirectView.as_view(pattern_name="home")),
    path("gazettes/<str:code>/", views.JurisdictionView.as_view(), name="jurisdiction"),
    path("gazettes/<str:code>/<int:year>", views.YearView.as_view(), name="year"),
    re_path(
        r"^gazettes/(?P<key>.{5,})$", views.OldGazetteView.as_view(), name="gazette_old"
    ),
    path("", include("peachjam.urls")),
]
