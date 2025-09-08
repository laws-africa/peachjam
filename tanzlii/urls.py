from django.urls import include, path
from django.views.generic.base import RedirectView

from tanzlii import views

urlpatterns = [
    path("paralegals/", views.ParalegalsView.as_view(), name="paralegals"),
    path("taxonomy/paralegals", RedirectView.as_view(pattern_name="paralegals")),
    path(
        "taxonomy/paralegals/paralegals",
        RedirectView.as_view(pattern_name="paralegals"),
    ),
    path("", include("peachjam_ml.urls")),
    path("", include("liiweb.urls")),
]
