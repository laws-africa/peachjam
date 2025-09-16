from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from django.views.generic.base import RedirectView

from tanzlii import views

urlpatterns = i18n_patterns(
    path("paralegals/", views.ParalegalsView.as_view(), name="paralegals"),
    path("taxonomy/paralegals", RedirectView.as_view(pattern_name="paralegals")),
    path(
        "taxonomy/paralegals/paralegals",
        RedirectView.as_view(pattern_name="paralegals"),
    ),
    path("", include("peachjam_ml.urls")),
    path("", include("liiweb.urls")),
) + [
    path("", include("liiweb.urls_non_i18n")),
]
