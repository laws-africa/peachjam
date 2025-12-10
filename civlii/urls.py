from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

urlpatterns = i18n_patterns(
    path("", include("peachjam_ml.urls")),
    path("", include("liiweb.urls.i18n")),
) + [
    path("", include("liiweb.urls.non_i18n")),
]
