from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from peachjam.views import RobotsView
from peachjam.views.generic_views import CSRFTokenView

# these urls do NOT get i18n language prefixes
urlpatterns = [
    path("feeds/", include("peachjam.urls.feeds")),
    path("api/", include("peachjam_api.urls")),
    path("i18n/", include("peachjam.urls.i18n")),
    path("_token", CSRFTokenView.as_view(), name="csrf_token"),
    path(
        "robots.txt",
        RobotsView.as_view(
            template_name="peachjam/robots.txt", content_type="text/plain"
        ),
    ),
    # django-markdown-editor for admin area
    path("martor/", include("martor.urls")),
    # offline documents
    path("", include("peachjam.urls.offline")),
    # other apps
    path("api/", include("peachjam_api.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = (
        [
            path("__debug__/", include(debug_toolbar.urls)),
        ]
        + urlpatterns
        + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    )
