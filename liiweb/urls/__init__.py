from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

# This sets the default urlpatterns for liiweb websites that don't define their own.
# If the settings use multiple languages, then we use i18n_patterns.
#
# If the LII wants to provide additional URLs, it MUST define its own urls.py and do
# something similar since i18n_patterns must be called in the root urls.py.

urlpatterns = [path("", include("liiweb.urls.i18n"))]

if len(settings.LANGUAGES) > 1:
    # multi-lingual site
    urlpatterns = i18n_patterns(*urlpatterns)

urlpatterns = urlpatterns + [path("", include("liiweb.urls.non_i18n"))]
