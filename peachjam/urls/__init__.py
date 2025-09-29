# flake8: noqa
from django.conf import settings

# cache duration for most cached pages
CACHE_DURATION = 60 * 60 * 24


from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

urlpatterns = [path("", include("peachjam.urls.i18n"))]

if len(settings.LANGUAGES) > 1:
    # multi-lingual site
    urlpatterns = i18n_patterns(*urlpatterns)

urlpatterns = urlpatterns + [path("", include("peachjam.urls.non_i18n"))]
